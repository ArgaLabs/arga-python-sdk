from __future__ import annotations

import httpx
import pytest
import respx

from arga_sdk import Arga, AsyncArga, Run, RunDetail
from arga_sdk.exceptions import ArgaError

from .conftest import (
    RUN_DETAIL_COMPLETED,
    RUN_DETAIL_RUNNING,
    RUN_RESPONSE,
    TEST_API_KEY,
    TEST_BASE_URL,
)


# --------------------------------------------------------------------------
# Sync tests
# --------------------------------------------------------------------------


class TestCreateUrlRun:
    def test_basic(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/validate/url-run").mock(
            return_value=httpx.Response(200, json=RUN_RESPONSE)
        )
        run = client.runs.create_url_run("https://staging.example.com")

        assert isinstance(run, Run)
        assert run.run_id == "run_abc123"
        assert run.status == "running"
        assert run.session_id == "sess_xyz"

        # Verify the request body
        request = route.calls[0].request
        assert request.headers["authorization"] == f"Bearer {TEST_API_KEY}"
        body = _json_body(request)
        assert body == {"url": "https://staging.example.com"}

    def test_with_all_options(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/validate/url-run").mock(
            return_value=httpx.Response(200, json=RUN_RESPONSE)
        )
        client.runs.create_url_run(
            "https://staging.example.com",
            prompt="Test the checkout flow",
            twins=["stripe"],
            credentials={"username": "admin", "password": "secret"},
            runner_mode="headed",
            session_id="sess_custom",
        )

        body = _json_body(route.calls[0].request)
        assert body["url"] == "https://staging.example.com"
        assert body["prompt"] == "Test the checkout flow"
        assert body["twins"] == ["stripe"]
        assert body["credentials"] == {"username": "admin", "password": "secret"}
        assert body["runner_mode"] == "headed"
        assert body["session_id"] == "sess_custom"


class TestCreatePrRun:
    def test_basic(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/validate/pr-run").mock(
            return_value=httpx.Response(200, json=RUN_RESPONSE)
        )
        run = client.runs.create_pr_run("owner/repo", branch="feature-x")

        assert isinstance(run, Run)
        assert run.run_id == "run_abc123"

        body = _json_body(route.calls[0].request)
        assert body == {"repo": "owner/repo", "branch": "feature-x"}

    def test_with_all_options(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/validate/pr-run").mock(
            return_value=httpx.Response(200, json=RUN_RESPONSE)
        )
        client.runs.create_pr_run(
            "owner/repo",
            branch="feature-x",
            pr_url="https://github.com/owner/repo/pull/42",
            context_notes="Changed the auth module",
            scenario_prompt="Verify login still works",
            twins=["stripe", "plaid"],
            frontend_url="https://preview.example.com",
            session_id="sess_pr",
        )

        body = _json_body(route.calls[0].request)
        assert body["repo"] == "owner/repo"
        assert body["branch"] == "feature-x"
        assert body["pr_url"] == "https://github.com/owner/repo/pull/42"
        assert body["context_notes"] == "Changed the auth module"
        assert body["scenario_prompt"] == "Verify login still works"
        assert body["twins"] == ["stripe", "plaid"]
        assert body["frontend_url"] == "https://preview.example.com"
        assert body["session_id"] == "sess_pr"


class TestCreateAgentRun:
    def test_basic(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/validate/pr-run").mock(
            return_value=httpx.Response(200, json=RUN_RESPONSE)
        )
        run = client.runs.create_agent_run("owner/repo", branch="main")

        assert isinstance(run, Run)
        assert run.run_id == "run_abc123"

        body = _json_body(route.calls[0].request)
        assert body["repo"] == "owner/repo"
        assert body["branch"] == "main"
        assert body["run_type"] == "agent_run"

    def test_with_all_options(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/validate/pr-run").mock(
            return_value=httpx.Response(200, json=RUN_RESPONSE)
        )
        client.runs.create_agent_run(
            "owner/repo",
            branch="main",
            pr_url="https://github.com/owner/repo/pull/42",
            context_notes="Explore the auth flow",
            scenario_prompt="Seed login fixtures",
            twins=["github"],
            frontend_url="https://preview.example.com",
            session_id="sess_agent",
        )

        body = _json_body(route.calls[0].request)
        assert body["repo"] == "owner/repo"
        assert body["branch"] == "main"
        assert body["pr_url"] == "https://github.com/owner/repo/pull/42"
        assert body["context_notes"] == "Explore the auth flow"
        assert body["scenario_prompt"] == "Seed login fixtures"
        assert body["twins"] == ["github"]
        assert body["frontend_url"] == "https://preview.example.com"
        assert body["session_id"] == "sess_agent"
        assert body["run_type"] == "agent_run"


class TestGetRun:
    def test_get(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/runs/run_abc123").mock(
            return_value=httpx.Response(200, json=RUN_DETAIL_COMPLETED)
        )
        detail = client.runs.get("run_abc123")

        assert isinstance(detail, RunDetail)
        assert detail.id == "run_abc123"
        assert detail.run_id == "run_abc123"
        assert detail.status == "completed"
        assert detail.run_type == "url_run"
        assert detail.mode == "quick"
        assert detail.environment_url == "https://staging.example.com"
        assert detail.surface_urls == ["https://staging.example.com/home"]
        assert detail.twins == ["stripe", "plaid"]
        assert detail.results_json == {"tests": [{"name": "login", "passed": True}]}
        assert detail.story_json == {"summary": "All tests passed."}
        assert detail.created_at is not None


class TestCancelRun:
    def test_cancel(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.post("/validate/run_abc123/cancel").mock(
            return_value=httpx.Response(200, json={"status": "cancelled"})
        )
        result = client.runs.cancel("run_abc123")
        assert result == {"status": "cancelled"}


class TestWaitRun:
    def test_wait_completes(self, client: Arga, mock_router: respx.Router) -> None:
        """Polling returns running twice, then completed."""
        route = mock_router.get("/runs/run_abc123")
        route.side_effect = [
            httpx.Response(200, json=RUN_DETAIL_RUNNING),
            httpx.Response(200, json=RUN_DETAIL_RUNNING),
            httpx.Response(200, json=RUN_DETAIL_COMPLETED),
        ]

        detail = client.runs.wait("run_abc123", poll_interval=0.01, timeout=5)
        assert detail.status == "completed"
        assert route.call_count == 3

    def test_wait_timeout(self, client: Arga, mock_router: respx.Router) -> None:
        """Polling should raise ArgaError on timeout."""
        mock_router.get("/runs/run_abc123").mock(
            return_value=httpx.Response(200, json=RUN_DETAIL_RUNNING)
        )
        with pytest.raises(ArgaError, match="Timed out"):
            client.runs.wait("run_abc123", poll_interval=0.01, timeout=0.05)


# --------------------------------------------------------------------------
# Async tests
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_create_url_run(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        route = router.post("/validate/url-run").mock(
            return_value=httpx.Response(200, json=RUN_RESPONSE)
        )
        run = await async_client.runs.create_url_run("https://staging.example.com")

        assert isinstance(run, Run)
        assert run.run_id == "run_abc123"

        body = _json_body(route.calls[0].request)
        assert body == {"url": "https://staging.example.com"}

    await async_client.close()


@pytest.mark.asyncio
async def test_async_get_run(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        router.get("/runs/run_abc123").mock(
            return_value=httpx.Response(200, json=RUN_DETAIL_COMPLETED)
        )
        detail = await async_client.runs.get("run_abc123")

        assert isinstance(detail, RunDetail)
        assert detail.status == "completed"

    await async_client.close()


@pytest.mark.asyncio
async def test_async_wait_completes(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        route = router.get("/runs/run_abc123")
        route.side_effect = [
            httpx.Response(200, json=RUN_DETAIL_RUNNING),
            httpx.Response(200, json=RUN_DETAIL_COMPLETED),
        ]

        detail = await async_client.runs.wait(
            "run_abc123", poll_interval=0.01, timeout=5
        )
        assert detail.status == "completed"
        assert route.call_count == 2

    await async_client.close()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _json_body(request: httpx.Request) -> dict:
    """Extract the JSON body from an httpx Request."""
    import json

    return json.loads(request.content)
