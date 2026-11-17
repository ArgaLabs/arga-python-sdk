import copy
import json
import stat
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from arga_sdk.tracing import CapturePolicy
from arga_sdk.tracing.braintrust import BraintrustSync, SyncError, project_trace

UTC = timezone.utc
PROJECT = "00000000-0000-0000-0000-000000000001"
SINCE = datetime(2026, 11, 17, 10, tzinfo=UTC)
CREATED = "2026-11-17T10:01:00+00:00"
POLICY = CapturePolicy(text_fields=frozenset({"goal", "policy"}))


def rows():
    return [
        {
            "span_id": "root",
            "root_span_id": "trace-raw-id",
            "input": "Refund ch_actual for customer@example.org.",
            "metrics": {"start": 1, "end": 6},
            "output": "FINAL_OUTPUT_CANARY",
            "metadata": {"api_key": "KEY_CANARY"},
        },
        {
            "span_id": "read",
            "root_span_id": "trace-raw-id",
            "span_parents": ["root"],
            "span_attributes": {"type": "tool", "name": "stripe.charges.retrieve"},
            "input": {"id": "ch_actual", "authorization": "Bearer AUTH_CANARY"},
            "output": {
                "id": "ch_actual",
                "amount": 4900,
                "amount_refunded": 1200,
                "currency": "usd",
                "customer": "cus_actual",
                "metadata": {"secret": "PAYLOAD_CANARY"},
            },
            "metrics": {"start": 2, "end": 3},
        },
        {
            "span_id": "refund",
            "root_span_id": "trace-raw-id",
            "span_parents": ["root"],
            "span_attributes": {"type": "tool", "name": "stripe.refunds.create"},
            "input": {"charge": "ch_actual", "amount": 3700},
            "output": {"id": "re_actual", "charge": "ch_actual", "amount": 3700, "status": "succeeded"},
            "metrics": {"start": 4, "end": 5},
        },
    ]


def project(data):
    return project_trace(data, source="support", project_id=PROJECT, alias_key=b"x" * 32, policy=POLICY)


def test_projection_drops_llm_payload_and_preserves_refund_context():
    episode = project(rows())
    assert episode.blockers() == []
    assert "CANARY" not in json.dumps(episode.payload())
    assert "trace-raw-id" not in json.dumps(episode.payload())
    assert episode.events[0].records[0].amount_refunded == 1200
    assert episode.events[0].records[0].id == episode.events[1].parameters.charge
    assert episode.events[0].records[0].id in episode.goal
    assert project(rows()).payload() == episode.payload()


def test_incomplete_trees_overlap_and_unknown_tools_do_not_become_ready():
    source = rows()
    source[1]["span_parents"] = ["missing"]
    with pytest.raises(SyncError, match="parents"):
        project(source)
    source = rows()
    source[2]["metrics"]["start"] = 2.5
    assert "source_incomplete" in project(source).blockers()
    source = rows()
    source[1]["span_attributes"]["name"] = "private_unknown_tool"
    assert "unsupported_operation" in project(source).blockers()
    assert "private_unknown_tool" not in json.dumps(project(source).payload())


def test_llm_payloads_cannot_become_executed_provider_evidence():
    source = rows()
    llm = copy.deepcopy(source[1])
    llm["span_id"] = "llm"
    llm["span_attributes"]["type"] = "llm"
    llm["output"]["amount"] = 999999
    source.append(llm)
    assert len(project(source).events) == 2


@respx.mock
def test_sync_retries_acknowledged_windows_and_late_revisions_without_uploading_credentials(tmp_path):
    spans = rows()
    payloads, queries = [], []
    failed = [True]

    def braintrust(request):
        queries.append(json.loads(request.content)["query"])
        assert request.headers["authorization"] == "Bearer BT_KEY_CANARY"
        data = [{"root_span_id": "trace-raw-id", "created": CREATED}] if "is_root = true" in queries[-1] else spans
        return httpx.Response(200, json={"data": data})

    def arga(request):
        assert request.headers["authorization"] == "Bearer ARGA_KEY_CANARY"
        assert "BT_KEY_CANARY" not in request.content.decode()
        payloads.append(json.loads(request.content))
        return (
            httpx.Response(503, text="ERROR_CANARY")
            if failed[0]
            else httpx.Response(201, json={"id": str(uuid.uuid4())})
        )

    respx.post("https://api.braintrust.dev/btql").mock(side_effect=braintrust)
    respx.post("https://api.argalabs.com/datasets/evidence").mock(side_effect=arga)
    path = tmp_path / "checkpoint.json"
    with BraintrustSync(
        source="support",
        project_id=PROJECT,
        braintrust_key="BT_KEY_CANARY",
        arga_key="ARGA_KEY_CANARY",
        state_path=path,
        since=SINCE,
        policy=POLICY,
    ) as sync:
        with pytest.raises(SyncError, match="not advanced"):
            sync.sync_once(until=SINCE + timedelta(minutes=2))
        initial = json.loads(path.read_text())
        assert initial["watermark"] == SINCE.isoformat()
        assert "KEY_CANARY" not in path.read_text()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        failed[0] = False
        assert sync.sync_once(until=SINCE + timedelta(minutes=2))["uploaded"] == 1
        assert payloads[0] == payloads[1]
        assert sync.sync_once(until=SINCE + timedelta(minutes=2))["unchanged"] == 1
        spans[1]["output"]["amount_refunded"] = 1500
        assert sync.sync_once(until=SINCE + timedelta(minutes=2))["uploaded"] == 1
    assert payloads[-1]["episode_id"] == payloads[0]["episode_id"]
    assert "created >=" not in next(query for query in queries if "WHERE root_span_id =" in query)
    assert "CANARY" not in json.dumps(payloads)


@respx.mock
def test_braintrust_pagination_and_configuration_changes_fail_closed(tmp_path):
    calls = []

    def braintrust(request):
        query = json.loads(request.content)["query"]
        calls.append(query)
        if "OFFSET" not in query:
            return httpx.Response(200, json={"data": []}, headers={"x-bt-cursor": "next"})
        return httpx.Response(200, json={"data": []})

    respx.post("https://api.braintrust.dev/btql").mock(side_effect=braintrust)
    args = dict(
        source="support",
        project_id=PROJECT,
        braintrust_key="key",
        arga_key="key",
        state_path=tmp_path / "state",
        since=SINCE,
    )
    with BraintrustSync(**args) as sync:
        assert sync.sync_once(until=SINCE + timedelta(minutes=1))["uploaded"] == 0
    assert "OFFSET 'next'" in calls[1]
    with BraintrustSync(**args, policy=POLICY) as sync:
        with pytest.raises(SyncError, match="configuration"):
            sync.sync_once(until=SINCE + timedelta(minutes=1))


@respx.mock
def test_unfinished_roots_are_revisited_after_their_lookback_window(tmp_path):
    spans = rows()
    spans[0]["metrics"].pop("end")
    queries = []
    first_window = [True]

    def braintrust(request):
        query = json.loads(request.content)["query"]
        queries.append(query)
        if "is_root = true" in query:
            return httpx.Response(
                200, json={"data": [{"root_span_id": "trace-raw-id", "created": CREATED}] if first_window[0] else []}
            )
        return httpx.Response(200, json={"data": spans})

    respx.post("https://api.braintrust.dev/btql").mock(side_effect=braintrust)
    upload = respx.post("https://api.argalabs.com/datasets/evidence").mock(
        return_value=httpx.Response(201, json={"id": str(uuid.uuid4())})
    )
    with BraintrustSync(
        source="support",
        project_id=PROJECT,
        braintrust_key="key",
        arga_key="key",
        state_path=tmp_path / "state",
        since=SINCE,
        policy=POLICY,
    ) as sync:
        result = sync.sync_once(until=SINCE + timedelta(minutes=5))
        assert result["pending"] == 1 and result["uploaded"] == 0 and not upload.called
        first_window[0] = False
        spans[0]["metrics"]["end"] = 6
        result = sync.sync_once(until=SINCE + timedelta(minutes=10))
        assert result["pending"] == 0 and result["uploaded"] == 1
        assert "created >=" not in queries[-1]
