from __future__ import annotations

import httpx
import pytest
import respx

from arga_sdk import Arga, AsyncArga

from .conftest import RUN_DETAIL_COMPLETED, TEST_BASE_URL


@pytest.mark.parametrize("status", ["canceled", "error", "timed_out"])
def test_sync_wait_returns_for_additional_terminal_statuses(
    client: Arga, mock_router: respx.Router, status: str
) -> None:
    route = mock_router.get("/runs/run_abc123").mock(
        return_value=httpx.Response(
            200, json={**RUN_DETAIL_COMPLETED, "status": status}
        )
    )

    detail = client.runs.wait("run_abc123", poll_interval=0.01, timeout=0.05)

    assert detail.status == status
    assert route.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["canceled", "error", "timed_out"])
async def test_async_wait_returns_for_additional_terminal_statuses(
    async_client: AsyncArga, status: str
) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        route = router.get("/runs/run_abc123").mock(
            return_value=httpx.Response(
                200, json={**RUN_DETAIL_COMPLETED, "status": status}
            )
        )

        detail = await async_client.runs.wait(
            "run_abc123", poll_interval=0.01, timeout=0.05
        )

        assert detail.status == status
        assert route.call_count == 1

    await async_client.close()
