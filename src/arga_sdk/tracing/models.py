"""Portable v1 wire contract. Keep in sync with validation-server/app/training/evidence_models.py.

Only projected evidence belongs here. Provider response objects must never be serialized into it.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

MAX_EVIDENCE_BYTES = 100_000
Alias = Annotated[
    str, StringConstraints(pattern=r"^(cus|pi|ch|re|msg|thread|draft|actor|label)_[a-f0-9]{24}$")
]
EmailAlias = Annotated[str, StringConstraints(pattern=r"^person_[a-f0-9]{24}@example\.invalid$")]
Text = Annotated[str, StringConstraints(max_length=4000)]
Resource = Literal["customers", "payment_intents", "charges", "refunds", "messages", "drafts", "profile"]
Verb = Literal[
    "retrieve", "get", "list", "search", "create", "update", "send", "modify", "trash", "untrash", "delete"
]
Issue = Literal[
    "unsupported_operation",
    "projection_failed",
    "record_limit",
    "event_limit",
    "payload_limit",
    "source_incomplete",
    "text_dropped",
    "agent_error",
]


SYSTEM_LABELS = frozenset(
    {
        "INBOX",
        "SENT",
        "DRAFT",
        "TRASH",
        "SPAM",
        "UNREAD",
        "STARRED",
        "IMPORTANT",
        "CHAT",
        "CATEGORY_PERSONAL",
        "CATEGORY_SOCIAL",
        "CATEGORY_PROMOTIONS",
        "CATEGORY_UPDATES",
        "CATEGORY_FORUMS",
    }
)
RESOURCE_FIELDS = {
    "customers": {"email"},
    "payment_intents": {"customer", "latest_charge", "amount", "currency", "status", "created"},
    "charges": {
        "customer",
        "payment_intent",
        "amount",
        "amount_refunded",
        "currency",
        "paid",
        "captured",
        "refunded",
        "status",
        "created",
    },
    "refunds": {"payment_intent", "charge", "amount", "currency", "status", "created"},
    "messages": {"thread_id", "from_email", "to", "subject", "body", "labels", "internal_date"},
    "drafts": {"message_id", "thread_id", "from_email", "to", "subject", "body", "labels", "internal_date"},
    "profile": {"email"},
}
STRIPE_RESOURCES = frozenset({"customers", "payment_intents", "charges", "refunds"})


def _record_schema(schema):
    # Portable constraints complement runtime checks (contiguous event sequence is dynamic).
    all_fields = set(schema["properties"]) - {"id", "resource"}
    schema["allOf"] = []
    for resource, fields in RESOURCE_FIELDS.items():
        allowed = {"from" if field == "from_email" else field for field in fields}
        schema["allOf"].append(
            {
                "if": {"properties": {"resource": {"const": resource}}, "required": ["resource"]},
                "then": {"not": {"anyOf": [{"required": [field]} for field in sorted(all_fields - allowed)]}},
            }
        )
    schema["properties"]["labels"]["anyOf"][0]["items"] = {
        "anyOf": [{"enum": sorted(SYSTEM_LABELS)}, {"type": "string", "pattern": "^label_[a-f0-9]{24}$"}]
    }


def _event_schema(schema):
    schema["allOf"] = [
        {
            "if": {"properties": {"resource": {"const": resource}}, "required": ["resource"]},
            "then": {
                "properties": {
                    "provider": {"const": "stripe" if resource in STRIPE_RESOURCES else "gmail"},
                    "records": {"items": {"properties": {"resource": {"const": resource}}}},
                }
            },
        }
        for resource in RESOURCE_FIELDS
    ]


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class Parameters(EvidenceModel):
    id: Alias | None = None
    customer: Alias | None = None
    payment_intent: Alias | None = None
    charge: Alias | None = None
    user: Alias | None = None
    amount: int | None = Field(default=None, ge=0, le=10**12)
    currency: str | None = Field(default=None, pattern=r"^[a-z]{3}$")


class Record(EvidenceModel):
    model_config = ConfigDict(json_schema_extra=_record_schema)
    resource: Resource
    id: Alias
    customer: Alias | None = None
    payment_intent: Alias | None = None
    charge: Alias | None = None
    latest_charge: Alias | None = None
    thread_id: Alias | None = None
    message_id: Alias | None = None
    email: EmailAlias | None = None
    from_email: EmailAlias | None = Field(default=None, alias="from")
    to: list[EmailAlias] | None = Field(default=None, max_length=20)
    subject: Text | None = None
    body: Text | None = None
    labels: list[str] | None = Field(default=None, max_length=30)
    amount: int | None = Field(default=None, ge=0, le=10**12)
    amount_refunded: int | None = Field(default=None, ge=0, le=10**12)
    currency: str | None = Field(default=None, pattern=r"^[a-z]{3}$")
    paid: bool | None = None
    captured: bool | None = None
    refunded: bool | None = None
    status: (
        Literal[
            "succeeded",
            "pending",
            "failed",
            "canceled",
            "requires_payment_method",
            "requires_confirmation",
            "requires_action",
            "processing",
            "requires_capture",
        ]
        | None
    ) = None
    created: int | None = Field(default=None, ge=0, le=253402300799)
    internal_date: int | None = Field(default=None, ge=0, le=253402300799000)

    @model_validator(mode="after")
    def fields_for_resource(self):
        fields = self.model_fields_set - {"id", "resource"}
        allowed = RESOURCE_FIELDS[self.resource]
        if fields - allowed:
            raise ValueError("Fields do not belong to this resource")
        if self.labels is not None:
            import re

            if any(
                label not in SYSTEM_LABELS and not re.fullmatch(r"label_[a-f0-9]{24}", label)
                for label in self.labels
            ):
                raise ValueError("Labels must be system labels or local aliases")
        return self


class Error(EvidenceModel):
    category: Literal["provider", "permission", "rate_limit", "network", "unknown"]
    http_status: int | None = Field(default=None, ge=400, le=599)
    code: (
        Literal[
            "rate_limit",
            "resource_missing",
            "permission_denied",
            "invalid_request",
            "insufficient_funds",
            "other",
        ]
        | None
    ) = None


class Event(EvidenceModel):
    model_config = ConfigDict(json_schema_extra=_event_schema)
    sequence: int = Field(ge=1, le=100)
    provider: Literal["gmail", "stripe"]
    resource: Resource
    verb: Verb
    parameters: Parameters = Field(default_factory=Parameters)
    records: list[Record] = Field(default_factory=list, max_length=50)
    scope: Literal["resource", "result_page", "mutation"]
    complete: bool | None = None
    error: Error | None = None

    @model_validator(mode="after")
    def resource_matches(self):
        if (self.resource in STRIPE_RESOURCES) != (self.provider == "stripe"):
            raise ValueError("Provider and resource disagree")
        if any(record.resource != self.resource for record in self.records):
            raise ValueError("Record and event resource disagree")
        return self


class Episode(EvidenceModel):
    schema_version: Literal["arga.evidence.v1"] = "arga.evidence.v1"
    source: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    origin: Literal["sdk", "braintrust"] = "sdk"
    episode_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    policy_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    goal: Text | None = None
    policies: list[Text] = Field(default_factory=list, max_length=10)
    events: list[Event] = Field(default_factory=list, max_length=100)
    issues: list[Issue] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def ordered_events(self):
        if [event.sequence for event in self.events] != list(range(1, len(self.events) + 1)):
            raise ValueError("Events must have contiguous sequence numbers")
        return self

    def payload(self):
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)

    def blockers(self) -> list[str]:
        reasons = [issue for issue in self.issues if issue not in {"agent_error", "text_dropped"}]
        if not self.goal:
            reasons.append("missing_goal")
        if not any(event.scope in {"resource", "result_page"} and event.records for event in self.events):
            reasons.append("missing_starting_state")
        return reasons
