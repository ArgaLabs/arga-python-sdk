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
    key_route = mock_router.post("/datasets/evidence-key").mock(return_value=httpx.Response(200, json=response()))
    key = client.training.create_upload_key(source="support")
    assert key_route.called and "NEVER_REPR_THIS" not in repr(key)
    assert key.key.get_secret_value() == "arga_trace_NEVER_REPR_THIS"
    route = mock_router.post("/datasets/evidence").mock(return_value=httpx.Response(201, json={"id": "dataset"}))
    episode = Episode(source="support", episode_id="a" * 32, policy_hash="b" * 64)
    assert client.training.upload_evidence(episode) == {"id": "dataset"}
    assert route.called


@pytest.mark.asyncio
async def test_async_training_namespace(async_client, mock_router):
    mock_router.post("/datasets/evidence-key").mock(return_value=httpx.Response(200, json=response()))
    key = await async_client.training.create_upload_key(source="support")
    assert "NEVER_REPR_THIS" not in repr(key)
