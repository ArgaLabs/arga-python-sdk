import asyncio
import base64
import copy
import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
import respx

from arga_sdk.tracing import CapturePolicy, init
from arga_sdk.tracing.models import Episode

POLICY = CapturePolicy(
    text_fields=frozenset({"goal", "policy", "gmail.subject", "gmail.body"}),
    transform_text=lambda text: text.replace("Private Person", "Customer"),
)
KEY = b"a" * 32
CHARGE = {
    "id": "ch_actual",
    "customer": "cus_actual",
    "payment_intent": "pi_actual",
    "amount": 4900,
    "currency": "usd",
    "paid": True,
    "captured": True,
    "amount_refunded": 1200,
    "metadata": {"secret": "METADATA_CANARY"},
    "billing_details": {"address": "ADDRESS_CANARY"},
}
MESSAGE = {
    "id": "provider-message-id",
    "threadId": "provider-thread-id",
    "internalDate": "1794924000000",
    "labelIds": ["INBOX", "PRIVATE_LABEL_CANARY"],
    "snippet": "SNIPPET_CANARY",
    "raw": "RAW_MIME_CANARY",
    "payload": {
        "mimeType": "text/plain",
        "headers": [
            {"name": "From", "value": "Private Person <private@example.org>"},
            {"name": "To", "value": "support@example.org"},
            {"name": "Subject", "value": "Refund for Private Person ch_actual"},
            {"name": "X-Secret", "value": "HEADER_CANARY"},
        ],
        "body": {
            "data": base64.urlsafe_b64encode(
                b"Refund ch_actual for private@example.org; Private Person"
            ).decode()
        },
        "parts": [
            {
                "mimeType": "application/pdf",
                "filename": "ATTACHMENT_NAME_CANARY",
                "body": {"data": "ATTACHMENT_CANARY"},
            }
        ],
    },
}


def test_allowlist_aliases_and_provider_results_are_unchanged():
    tracing = init(source="support", policy=POLICY, alias_key=KEY, upload=False)
    raw_charge, raw_message = copy.deepcopy(CHARGE), copy.deepcopy(MESSAGE)

    class Request:
        def execute(self, **kwargs):
            return raw_message

    class Gmail:
        def users(self):
            return self

        def messages(self):
            return self

        def get(self, **kwargs):
            return Request()

    stripe = tracing.wrap_stripe(
        SimpleNamespace(v1=SimpleNamespace(charges=SimpleNamespace(retrieve=lambda *a, **kw: raw_charge)))
    )
    gmail = tracing.wrap_gmail(Gmail())
    with tracing.episode(
        goal="Refund ch_actual for Private Person private@example.org",
        policies=["Confirmations require owner review."],
    ):
        assert stripe.v1.charges.retrieve("ch_actual", options={"api_key": "KEY_CANARY"}) is raw_charge
        assert gmail.users().messages().get(userId="me", id="provider-message-id").execute() is raw_message
    payload = tracing.last_episode
    encoded = json.dumps(payload)
    for forbidden in [
        "CANARY",
        "private@example.org",
        "Private Person",
        "ch_actual",
        "cus_actual",
        "pi_actual",
        "provider-message-id",
        "provider-thread-id",
        "billing_details",
        "metadata",
        "api_key",
    ]:
        assert forbidden not in encoded
    assert raw_charge == CHARGE and raw_message == MESSAGE
    episode = Episode.model_validate(payload)
    charge, message = episode.events[0].records[0], episode.events[1].records[0]
    assert charge.amount == 4900 and charge.amount_refunded == 1200
    assert charge.id in episode.goal and charge.id in message.subject and charge.id in message.body
    assert message.from_email in episode.goal and message.from_email in message.body
    assert episode.blockers() == []


def test_text_is_off_by_default_and_failed_filter_fails_closed():
    tracing = init(source="support", alias_key=KEY, upload=False)
    with tracing.episode(goal="GOAL_CANARY"):
        tracing.call(lambda: MESSAGE, ("gmail", "messages", "get"), {}, (), {})
    payload = tracing.last_episode
    assert "GOAL_CANARY" not in json.dumps(payload)
    assert "subject" not in payload["events"][0]["records"][0]
    assert "body" not in payload["events"][0]["records"][0]
    assert "missing_goal" in Episode.model_validate(payload).blockers()

    def broken(text):
        raise ValueError("FILTER_SECRET_CANARY")

    tracing = init(
        source="support",
        policy=CapturePolicy(text_fields=frozenset({"goal", "gmail.subject"}), transform_text=broken),
        upload=False,
    )
    with tracing.episode(goal="SECRET_CANARY"):
        assert tracing.call(lambda: MESSAGE, ("gmail", "messages", "get"), {}, (), {}) is MESSAGE
    assert tracing.last_episode["issues"] == ["projection_failed"]
    assert "CANARY" not in json.dumps(tracing.last_episode)


def test_errors_unknown_operations_and_record_caps_never_export_raw_payloads():
    tracing = init(source="support", policy=POLICY, upload=False)
    error = RuntimeError("ERROR_CANARY")
    error.http_status = 403
    error.code = "PROVIDER_CODE_CANARY"

    def fail():
        raise error

    with tracing.episode(goal="Refund the duplicate."):
        with pytest.raises(RuntimeError) as raised:
            tracing.call(fail, ("stripe", "charges", "retrieve"), {}, (), {})
        assert raised.value is error
        tracing.call(lambda: {"secret": "UNKNOWN_CANARY"}, None, {"secret": "INPUT_CANARY"}, (), {})
        tracing.call(
            lambda: {"data": [CHARGE] * 51, "has_more": False}, ("stripe", "charges", "list"), {}, (), {}
        )
    payload = tracing.last_episode
    assert "CANARY" not in json.dumps(payload)
    assert payload["events"][0]["error"] == {"category": "permission", "http_status": 403, "code": "other"}
    assert {"record_limit", "unsupported_operation"} <= set(payload["issues"])
    assert len(payload["events"][1]["records"]) == 50
    assert payload["events"][1]["complete"] is False


@pytest.mark.asyncio
async def test_async_agents_isolate_context_and_return_original_results():
    tracing = init(source="support", policy=POLICY, upload=False)
    episodes = []
    tracing.submit = lambda episode: episodes.append(episode.payload())

    async def retrieve(charge):
        await asyncio.sleep(0)
        return {**CHARGE, "id": charge}

    stripe = tracing.wrap_stripe(
        SimpleNamespace(v1=SimpleNamespace(charges=SimpleNamespace(retrieve_async=retrieve)))
    )

    @tracing.agent(goal=lambda charge: "Refund " + charge)
    async def agent(charge):
        return await stripe.v1.charges.retrieve_async(charge)

    results = await asyncio.gather(agent("ch_one"), agent("ch_two"))
    assert [result["id"] for result in results] == ["ch_one", "ch_two"]
    assert len(episodes) == 2 and episodes[0]["episode_id"] != episodes[1]["episode_id"]
    assert all(len(episode["events"]) == 1 for episode in episodes)
    assert all(episode["events"][0]["records"][0]["id"] in episode["goal"] for episode in episodes)
    assert tracing.current() is None


@respx.mock
def test_exporter_retries_only_projected_payload_and_preserves_agent_on_rejection(caplog):
    received = []
    dataset_id = str(uuid.uuid4())

    def upload(request):
        received.append(json.loads(request.content))
        if len(received) == 1:
            return httpx.Response(503, text="SERVER_SECRET_CANARY")
        return httpx.Response(201, json={"id": dataset_id})

    route = respx.post("https://ingest.example.test/datasets/evidence").mock(side_effect=upload)
    tracing = init(
        source="support",
        policy=POLICY,
        api_key="arga_trace_LOCAL_KEY_CANARY",
        base_url="https://ingest.example.test",
    )
    with tracing:
        with tracing.episode(goal="Refund ch_actual"):
            tracing.call(
                lambda: CHARGE,
                ("stripe", "charges", "retrieve"),
                {"id": "ch_actual", "headers": {"Authorization": "HEADER_SECRET_CANARY"}},
                (),
                {},
            )
        assert tracing.flush()
        assert tracing.exporter.stats["uploaded"] == 1
        assert tracing.exporter.receipts[-1]["training_path"] == "/training/" + dataset_id
    assert route.call_count == 2 and received[0] == received[1]
    assert "CANARY" not in json.dumps(received)
    assert "CANARY" not in caplog.text


def test_real_google_client_request_is_observed_only_when_executed():
    discovery = pytest.importorskip("googleapiclient.discovery")
    httplib2 = pytest.importorskip("httplib2")

    class HTTP:
        calls = 0

        def request(self, *args, **kwargs):
            self.calls += 1
            return httplib2.Response({"status": "200"}), json.dumps(MESSAGE).encode()

    http = HTTP()
    service = discovery.build("gmail", "v1", http=http, static_discovery=True)
    tracing = init(source="support", policy=POLICY, upload=False)
    gmail = tracing.wrap_gmail(service)
    with tracing.episode(goal="Refund the duplicate") as episode:
        request = gmail.users().messages().get(userId="me", id="provider-message-id", format="full")
        assert not episode.preview()["events"]
        assert request.execute() == MESSAGE
    assert http.calls == 1 and len(tracing.last_episode["events"]) == 1


@pytest.mark.asyncio
async def test_real_stripe_client_sync_and_async():
    stripe = pytest.importorskip("stripe")

    class HTTP(stripe.HTTPClient):
        name = "test"

        def request(self, *args, **kwargs):
            return json.dumps({"object": "charge", **CHARGE}), 200, {}

        async def request_async(self, *args, **kwargs):
            return json.dumps({"object": "charge", **CHARGE}).encode(), 200, {}

    tracing = init(source="support", policy=POLICY, upload=False)
    client = tracing.wrap_stripe(stripe.StripeClient("sk_test_DO_NOT_SEND_TO_ARGA", http_client=HTTP()))
    with tracing.episode(goal="Refund ch_actual"):
        sync_result = client.v1.charges.retrieve("ch_actual")
        async_result = await client.v1.charges.retrieve_async("ch_actual")
    assert sync_result.id == async_result.id == "ch_actual"
    assert len(tracing.last_episode["events"]) == 2
    assert "DO_NOT_SEND" not in json.dumps(tracing.last_episode)


@respx.mock
def test_permanent_export_rejection_preserves_decorated_agent_result():
    route = respx.post("https://api.argalabs.com/datasets/evidence").mock(
        return_value=httpx.Response(422, text="PRIVATE_CANARY")
    )
    with init(source="support", policy=POLICY, api_key="test-key") as tracing:

        @tracing.agent(goal=lambda: "Inspect the charge")
        def agent():
            return tracing.call(lambda: CHARGE, ("stripe", "charges", "retrieve"), {}, (), {})

        assert agent() is CHARGE
        assert tracing.flush()
        assert tracing.diagnostics()["failed"] == 1
        assert tracing.recent_uploads() == []
    assert route.call_count == 1


def test_stripe_unsupported_classes_and_exception_types_are_preserved():
    import stripe

    tracing = init(source="support", upload=False)
    wrapped = tracing.wrap_stripe(stripe)
    assert wrapped.Invoice is stripe.Invoice
    assert wrapped.error.StripeError is stripe.error.StripeError
    with pytest.raises(wrapped.error.StripeError):
        raise stripe.error.StripeError("test")


@pytest.mark.parametrize(
    "parts,issue", [([b"\xff"], "projection_failed"), ([b"x" * 3000, b"y" * 3000], "payload_limit")]
)
def test_invalid_or_oversized_gmail_body_keeps_metadata(parts, issue):
    message = copy.deepcopy(MESSAGE)
    message["payload"].pop("body")
    message["payload"]["parts"] = [
        {"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(part).decode()}}
        for part in parts
    ]
    tracing = init(source="support", policy=POLICY, upload=False)
    with tracing.episode(goal="Inspect mail"):
        assert tracing.call(lambda: message, ("gmail", "messages", "get"), {}, (), {}) is message
    episode = Episode.model_validate(tracing.last_episode)
    assert issue in episode.blockers()
    assert episode.events[0].records[0].thread_id
    assert episode.events[0].records[0].body is None


@respx.mock
def test_final_validation_rejection_is_counted_without_upload():
    with init(source="support", api_key="test-key") as tracing:
        episode = Episode(source="support", episode_id="a" * 32, policy_hash="b" * 64)
        episode.issues = ["INVALID_PRIVATE_CANARY"]
        assert not tracing.submit(episode)
        assert tracing.diagnostics() == {"dropped": 1}


@pytest.mark.asyncio
async def test_concurrent_reads_are_complete_but_overlapping_mutation_is_not():
    tracing = init(source="support", policy=POLICY, upload=False)

    async def read():
        await asyncio.sleep(0)
        return CHARGE

    with tracing.episode(goal="Inspect charges"):
        await asyncio.gather(
            *(tracing.call_async(read, ("stripe", "charges", "retrieve"), {}, (), {}) for _ in range(2))
        )
    assert "source_incomplete" not in Episode.model_validate(tracing.last_episode).blockers()
    with tracing.episode(goal="Inspect and change charges"):
        await asyncio.gather(
            tracing.call_async(read, ("stripe", "charges", "retrieve"), {}, (), {}),
            tracing.call_async(read, ("stripe", "charges", "update"), {}, (), {}),
        )
    assert "source_incomplete" in Episode.model_validate(tracing.last_episode).blockers()
