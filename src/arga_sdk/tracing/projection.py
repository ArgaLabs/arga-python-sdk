"""Customer-side selection. Never traverse arbitrary provider metadata or serialize responses."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from email.utils import getaddresses

from .models import (
    MAX_EVIDENCE_BYTES,
    RESOURCE_FIELDS,
    SYSTEM_LABELS,
    Episode,
    Error,
    Event,
    Parameters,
    Record,
)

TEXT_FIELDS = frozenset({"goal", "policy", "gmail.subject", "gmail.body"})
READS = {"get", "retrieve", "list", "search"}
PREFIXES = {
    "customers": "cus",
    "payment_intents": "pi",
    "charges": "ch",
    "refunds": "re",
    "messages": "msg",
    "drafts": "draft",
    "profile": "actor",
}
EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RESOURCE_ID = re.compile(r"\b(cus|pi|ch|re)_[A-Za-z0-9_]+\b")
SECRET = re.compile(
    r"(?i)(?:Bearer\s+\S+|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]+|sk-ant-[A-Za-z0-9_-]+|ya29\.[A-Za-z0-9._-]+|(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[^\s,;]+)"
)


@dataclass(frozen=True)
class CapturePolicy:
    """No free text leaves by default. Selected text still needs a customer-appropriate filter.

    transform_text runs locally before aliases/credential masking. It must never call an
    Arga-hosted service with raw text. Names and proprietary facts cannot be reliably
    removed by generic regular expressions; use this callback for those requirements.
    """

    text_fields: frozenset[str] = frozenset()
    transform_text: Callable[[str], str] | None = field(default=None, repr=False)
    revision: str = "1"

    def __post_init__(self):
        object.__setattr__(self, "text_fields", frozenset(self.text_fields))
        if self.text_fields - TEXT_FIELDS:
            raise ValueError("Unsupported text field")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", self.revision):
            raise ValueError("Invalid local policy revision")

    @property
    def fingerprint(self):
        config = {
            "text_fields": sorted(self.text_fields),
            "revision": self.revision,
            "custom_filter": self.transform_text is not None,
        }
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def value(obj, key, default=None):
    # StripeObject and Google API responses are mappings. Do not invoke generic
    # to_dict/model_dump/repr on an untrusted object, or inspect arbitrary attrs.
    return obj.get(key, default) if isinstance(obj, Mapping) else default


class Projector:
    def __init__(
        self, *, source: str, episode_key: str, alias_key: bytes, policy: CapturePolicy, origin="sdk"
    ):
        if len(alias_key) < 32:
            raise ValueError("Alias key must contain at least 32 bytes")
        self.key = hmac.digest(alias_key, episode_key.encode(), "sha256")
        self.policy = policy
        self.episode = Episode(
            source=source,
            origin=origin,
            episode_id=hmac.digest(self.key, b"episode-id", "sha256").hex()[:32],
            policy_hash=policy.fingerprint,
        )

    def issue(self, reason):
        if reason not in self.episode.issues:
            self.episode.issues.append(reason)

    def alias(self, prefix, original):
        if not isinstance(original, str) or not original:
            return None
        digest = hmac.new(self.key, (prefix + ":" + original).encode(), hashlib.sha256).hexdigest()[:24]
        return prefix + "_" + digest

    def email(self, original):
        if not isinstance(original, str) or not original:
            return None
        return self.alias("person", original.strip().lower()) + "@example.invalid"

    def text(self, name, original):
        if not isinstance(original, str) or not original:
            return None
        if name not in self.policy.text_fields:
            self.issue("text_dropped")
            return None
        # Bound work before invoking a user hook. No silent truncation of task facts.
        if len(original) > 32_000:
            self.issue("payload_limit")
            return None
        result = self.policy.transform_text(original) if self.policy.transform_text else original
        if not isinstance(result, str) or len(result) > 4000:
            self.issue("projection_failed")
            return None
        result = SECRET.sub("[credential removed]", result)
        result = EMAIL.sub(lambda m: self.email(m.group()), result)
        return RESOURCE_ID.sub(lambda m: self.alias(m.group(1), m.group()), result)

    def set_goal(self, goal, policies=()):
        try:
            self.episode.goal = self.text("goal", goal)
            if len(policies) > 10:
                self.issue("payload_limit")
            self.episode.policies = [text for item in policies[:10] if (text := self.text("policy", item))]
        except Exception:
            self.issue("projection_failed")

    def parameters(self, provider, resource, args):
        projected = {}
        for key, prefix in {
            "id": PREFIXES[resource],
            "customer": "cus",
            "payment_intent": "pi",
            "charge": "ch",
        }.items():
            if alias := self.alias(prefix, value(args, key)):
                projected[key] = alias
        if provider == "gmail":
            if alias := self.alias("actor", value(args, "userId", "me")):
                projected["user"] = alias
        else:
            amount, currency = value(args, "amount"), value(args, "currency")
            if type(amount) is int:
                projected["amount"] = amount
            if isinstance(currency, str) and re.fullmatch(r"[a-zA-Z]{3}", currency):
                projected["currency"] = currency.lower()
        return Parameters.model_validate(projected)

    def stripe_record(self, resource, raw):
        fields = {"resource": resource, "id": self.alias(PREFIXES[resource], value(raw, "id"))}
        allowed = RESOURCE_FIELDS[resource] - {"email"}
        refs = {"customer": "cus", "payment_intent": "pi", "charge": "ch", "latest_charge": "ch"}
        for key in allowed:
            item = value(raw, key)
            if key in refs:
                item = self.alias(refs[key], value(item, "id") if isinstance(item, Mapping) else item)
            if item is not None:
                fields[key] = item
        if resource == "customers" and (email := self.email(value(raw, "email"))):
            fields["email"] = email
        return Record.model_validate(fields)

    def gmail_record(self, resource, raw):
        original = raw
        if resource == "profile":
            return Record(
                resource="profile", id=self.alias("actor", "me"), email=self.email(value(raw, "emailAddress"))
            )
        if resource == "drafts":
            raw = value(raw, "message", {})
        fields = {"resource": resource, "id": self.alias(PREFIXES[resource], value(original, "id"))}
        if resource == "drafts" and (alias := self.alias("msg", value(raw, "id"))):
            fields["message_id"] = alias
        if alias := self.alias("thread", value(raw, "threadId")):
            fields["thread_id"] = alias
        date = value(raw, "internalDate")
        if isinstance(date, str) and date.isdigit():
            fields["internal_date"] = int(date)
        labels = value(raw, "labelIds")
        if isinstance(labels, list):
            if len(labels) > 30:
                self.issue("record_limit")
            fields["labels"] = [
                label if label in SYSTEM_LABELS else self.alias("label", label) for label in labels[:30]
            ]
        payload = value(raw, "payload", {})
        headers = value(payload, "headers", [])
        # Header names are matched locally; only selected headers are ever used.
        for header in headers if isinstance(headers, list) else []:
            name, content = value(header, "name", "").lower(), value(header, "value")
            if name == "subject":
                if text := self.text("gmail.subject", content):
                    fields["subject"] = text
            elif name in {"from", "to"} and isinstance(content, str):
                addresses = [self.email(address) for _, address in getaddresses([content]) if address]
                if name == "from" and addresses:
                    fields["from"] = addresses[0]
                elif name == "to":
                    if len(addresses) > 20:
                        self.issue("record_limit")
                    fields["to"] = addresses[:20]
        # Never inspect attachments, raw MIME, HTML, snippets, or arbitrary nested parts.
        if "gmail.body" in self.policy.text_fields:
            parts = [payload, *value(payload, "parts", [])][:20]
            texts = []
            for part in parts:
                if value(part, "mimeType") != "text/plain" or value(part, "filename"):
                    continue
                data = value(value(part, "body", {}), "data")
                if isinstance(data, str):
                    if len(data) > 44_000:
                        self.issue("payload_limit")
                        continue
                    try:
                        decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8")
                    except (ValueError, UnicodeError):
                        self.issue("projection_failed")
                        continue
                    text = self.text("gmail.body", decoded)
                    if text:
                        texts.append(text)
            if texts:
                body = "\n".join(texts)
                if len(body) > 4000:
                    self.issue("payload_limit")
                else:
                    fields["body"] = body
        return Record.model_validate(fields)

    def record(self, provider, resource, verb, args, response=None, error=None):
        """Executed calls only. A failed projection never changes the provider result."""
        if len(self.episode.events) >= 100:
            self.issue("event_limit")
            return
        try:
            read = verb in READS
            scope = "result_page" if verb in {"list", "search"} else "resource" if read else "mutation"
            items = []
            complete = None
            if response is not None:
                if scope == "result_page":
                    items = value(response, "data" if provider == "stripe" else resource, [])
                    if not isinstance(items, list):
                        raise ValueError("Invalid provider page")
                    if provider == "stripe":
                        more = value(response, "has_more")
                        complete = not more if type(more) is bool else None
                    else:
                        complete = not bool(value(response, "nextPageToken"))
                elif value(response, "id") or resource == "profile":
                    items = [response]
                    complete = True if read else None
                elif read:
                    raise ValueError("Missing provider resource")
            if len(items) > 50:
                self.issue("record_limit")
                complete = False
            records = [
                (
                    self.stripe_record(resource, item)
                    if provider == "stripe"
                    else self.gmail_record(resource, item)
                )
                for item in items[:50]
            ]
            event = Event(
                sequence=len(self.episode.events) + 1,
                provider=provider,
                resource=resource,
                verb=verb,
                parameters=self.parameters(provider, resource, args),
                records=records,
                scope=scope,
                complete=complete,
                error=normalize_error(error) if error else None,
            )
            # Check the bounded, already-projected structure only.
            candidate = self.episode.model_copy(update={"events": [*self.episode.events, event]})
            if len(json.dumps(candidate.payload()).encode()) > MAX_EVIDENCE_BYTES:
                self.issue("payload_limit")
                return
            self.episode.events.append(event)
        except Exception:
            self.issue("projection_failed")


def normalize_error(error):
    status = (
        value(error, "http_status") if isinstance(error, Mapping) else getattr(error, "http_status", None)
    )
    if status is None and not isinstance(error, Mapping):
        status = getattr(getattr(error, "resp", None), "status", None)
    status = status if type(status) is int and 400 <= status <= 599 else None
    code = value(error, "code") if isinstance(error, Mapping) else getattr(error, "code", None)
    allowed = {"rate_limit", "resource_missing", "permission_denied", "invalid_request", "insufficient_funds"}
    return Error(
        category="permission"
        if status in {401, 403}
        else "rate_limit"
        if status == 429
        else "provider"
        if status
        else "unknown",
        http_status=status,
        code=code if code in allowed else "other",
    )
