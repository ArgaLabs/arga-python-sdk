import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from arga_sdk.tracing.models import Episode


def response():
    return {
        "key": "arga_trace_NEVER_REPR_THIS",
        "scope": "training:ingest",
        "source": "support",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }


def test_scoped_key_and_explicit_evidence_upload(client, mock_router):
    key_route = mock_router.post("/datasets/evidence-key").mock(
        return_value=httpx.Response(200, json=response())
    )
    key = client.training.create_upload_key(source="support")
    assert key_route.called and "NEVER_REPR_THIS" not in repr(key)
    assert json.loads(key_route.calls.last.request.content) == {"source": "support"}
    assert key.key.get_secret_value() == "arga_trace_NEVER_REPR_THIS"
    route = mock_router.post("/datasets/evidence").mock(
        return_value=httpx.Response(201, json={"id": "dataset"})
    )
    episode = Episode(source="support", episode_id="a" * 32, policy_hash="b" * 64)
    assert client.training.upload_evidence(episode) == {"id": "dataset"}
    assert json.loads(route.calls.last.request.content) == episode.payload()


@pytest.mark.asyncio
async def test_async_training_namespace(async_client, mock_router):
    key_route = mock_router.post("/datasets/evidence-key").mock(
        return_value=httpx.Response(200, json=response())
    )
    key = await async_client.training.create_upload_key(source="support")
    assert "NEVER_REPR_THIS" not in repr(key)

    assert json.loads(key_route.calls.last.request.content) == {"source": "support"}
    route = mock_router.post("/datasets/evidence").mock(
        return_value=httpx.Response(201, json={"id": "dataset"})
    )
    episode = Episode(source="support", episode_id="a" * 32, policy_hash="b" * 64)
    assert await async_client.training.upload_evidence(episode) == {"id": "dataset"}
    assert json.loads(route.calls.last.request.content) == episode.payload()


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_oversized_evidence_never_reaches_transport(client, async_client, mock_router, asynchronous):
    episode = Episode.model_validate(
        {
            "source": "support",
            "episode_id": "a" * 32,
            "policy_hash": "b" * 64,
            "events": [
                {
                    "sequence": 1,
                    "provider": "gmail",
                    "resource": "messages",
                    "verb": "list",
                    "scope": "result_page",
                    "records": [{"resource": "messages", "id": "msg_" + "a" * 24, "body": "x" * 4000}] * 30,
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="upload limit"):
        if asynchronous:
            await async_client.training.upload_evidence(episode)
        else:
            client.training.upload_evidence(episode)
    assert not mock_router.calls
