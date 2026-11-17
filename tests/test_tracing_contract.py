"""Executable compatibility fixture consumed by the Training backend tests too."""

import base64
import json
from pathlib import Path

from arga_sdk.tracing import CapturePolicy
from arga_sdk.tracing.models import Episode
from arga_sdk.tracing.projection import Projector


def support_episode():
    projector = Projector(
        source="support-agent",
        episode_key="synthetic-support-case",
        alias_key=b"fixture-key-32-bytes-do-not-use!!!",
        policy=CapturePolicy(text_fields=frozenset({"goal", "policy", "gmail.subject", "gmail.body"})),
    )
    projector.set_goal(
        "Correct duplicate charge ch_duplicate for customer@example.org. Preserve ch_original.",
        ["Customer confirmations require the accountable owner's review before sending."],
    )
    projector.record("gmail", "profile", "get", {"userId": "me"}, {"emailAddress": "support@example.org"})
    projector.record(
        "gmail",
        "messages",
        "get",
        {"userId": "me", "id": "message-original"},
        {
            "id": "message-original",
            "threadId": "thread-original",
            "labelIds": ["INBOX"],
            "internalDate": "1794924000000",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "customer@example.org"},
                    {"name": "To", "value": "support@example.org"},
                    {"name": "Subject", "value": "Duplicate charge"},
                ],
                "body": {
                    "data": base64.urlsafe_b64encode(
                        b"Please correct duplicate charge ch_duplicate and preserve ch_original."
                    ).decode()
                },
            },
            "raw": "RAW_CANARY",
            "snippet": "SNIPPET_CANARY",
        },
    )
    projector.record(
        "stripe",
        "customers",
        "retrieve",
        {"id": "cus_customer"},
        {
            "id": "cus_customer",
            "email": "customer@example.org",
            "name": "NAME_CANARY",
            "metadata": {"private": "METADATA_CANARY"},
        },
    )
    for payment, charge, refunded in [("pi_original", "ch_original", 0), ("pi_duplicate", "ch_duplicate", 1200)]:
        projector.record(
            "stripe",
            "charges",
            "retrieve",
            {"id": charge},
            {
                "id": charge,
                "payment_intent": payment,
                "customer": "cus_customer",
                "amount": 4900,
                "currency": "usd",
                "amount_refunded": refunded,
                "paid": True,
                "captured": True,
            },
        )
    projector.record(
        "stripe",
        "refunds",
        "list",
        {"charge": "ch_duplicate"},
        {
            "data": [
                {
                    "id": "re_prior",
                    "payment_intent": "pi_duplicate",
                    "charge": "ch_duplicate",
                    "amount": 1200,
                    "currency": "usd",
                    "status": "succeeded",
                }
            ],
            "has_more": False,
        },
    )
    projector.record(
        "stripe",
        "refunds",
        "create",
        {"charge": "ch_duplicate", "amount": 3700},
        {
            "id": "re_new",
            "payment_intent": "pi_duplicate",
            "charge": "ch_duplicate",
            "amount": 3700,
            "currency": "usd",
            "status": "succeeded",
        },
    )
    return projector.episode


def test_wire_contract_and_shared_fixture():
    directory = Path(__file__).parent / "fixtures"
    fixture = json.loads((directory / "support-evidence-v1.json").read_text())
    assert support_episode().payload() == fixture
    assert "CANARY" not in json.dumps(fixture)
    assert Episode.model_validate(fixture).blockers() == []
    assert Episode.model_json_schema() == json.loads((directory / "evidence-v1.schema.json").read_text())
