from __future__ import annotations

import httpx
import pytest
import respx

from arga import Arga, AsyncArga
from arga.exceptions import ArgaAPIError

from .conftest import TEST_BASE_URL


# --------------------------------------------------------------------------
# Sync tests
# --------------------------------------------------------------------------


class TestErrorHandling:
    def test_401_unauthorized(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/runs/run_abc123").mock(
            return_value=httpx.Response(
                401, json={"detail": "Invalid or expired API key"}
            )
        )
        with pytest.raises(ArgaAPIError) as exc_info:
            client.runs.get("run_abc123")

        err = exc_info.value
        assert err.status_code == 401
        assert "Invalid or expired API key" in err.message

    def test_404_not_found(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/runs/run_nonexistent").mock(
            return_value=httpx.Response(
                404, json={"detail": "Run not found"}
            )
        )
        with pytest.raises(ArgaAPIError) as exc_info:
            client.runs.get("run_nonexistent")

        err = exc_info.value
        assert err.status_code == 404
        assert "Run not found" in err.message

    def test_500_server_error(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.post("/validate/url-run").mock(
            return_value=httpx.Response(
                500, json={"detail": "Internal server error"}
            )
        )
        with pytest.raises(ArgaAPIError) as exc_info:
            client.runs.create_url_run("https://example.com")

        err = exc_info.value
        assert err.status_code == 500
        assert "Internal server error" in err.message

    def test_error_with_message_field(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        """API sometimes uses 'message' instead of 'detail'."""
        mock_router.get("/runs/run_abc123").mock(
            return_value=httpx.Response(
                403, json={"message": "Forbidden: insufficient permissions"}
            )
        )
        with pytest.raises(ArgaAPIError) as exc_info:
            client.runs.get("run_abc123")

        err = exc_info.value
        assert err.status_code == 403
        assert "Forbidden: insufficient permissions" in err.message

    def test_error_with_plain_text_body(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        """Non-JSON error response falls back to response text."""
        mock_router.get("/runs/run_abc123").mock(
            return_value=httpx.Response(502, text="Bad Gateway")
        )
        with pytest.raises(ArgaAPIError) as exc_info:
            client.runs.get("run_abc123")

        err = exc_info.value
        assert err.status_code == 502
        assert "Bad Gateway" in err.message

    def test_error_response_attribute(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        """ArgaAPIError should carry the original httpx.Response."""
        mock_router.get("/runs/run_abc123").mock(
            return_value=httpx.Response(
                429, json={"detail": "Rate limit exceeded"}
            )
        )
        with pytest.raises(ArgaAPIError) as exc_info:
            client.runs.get("run_abc123")

        err = exc_info.value
        assert err.response is not None
        assert err.response.status_code == 429

    def test_error_on_post(self, client: Arga, mock_router: respx.Router) -> None:
        """Errors on POST endpoints are handled the same way."""
        mock_router.post("/validate/twins/provision").mock(
            return_value=httpx.Response(
                422, json={"detail": "Validation error: twins field required"}
            )
        )
        with pytest.raises(ArgaAPIError) as exc_info:
            client.twins.provision(["nonexistent_twin"])

        err = exc_info.value
        assert err.status_code == 422
        assert "twins field required" in err.message


# --------------------------------------------------------------------------
# Async tests
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_401_unauthorized(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        router.get("/runs/run_abc123").mock(
            return_value=httpx.Response(
                401, json={"detail": "Invalid or expired API key"}
            )
        )
        with pytest.raises(ArgaAPIError) as exc_info:
            await async_client.runs.get("run_abc123")

        err = exc_info.value
        assert err.status_code == 401
        assert "Invalid or expired API key" in err.message

    await async_client.close()


@pytest.mark.asyncio
async def test_async_500_server_error(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        router.post("/validate/url-run").mock(
            return_value=httpx.Response(
                500, json={"detail": "Internal server error"}
            )
        )
        with pytest.raises(ArgaAPIError) as exc_info:
            await async_client.runs.create_url_run("https://example.com")

        err = exc_info.value
        assert err.status_code == 500

    await async_client.close()
