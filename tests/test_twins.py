from __future__ import annotations

import json

import httpx
import pytest
import respx

from arga import Arga, AsyncArga, Twin, TwinInstance, TwinProvisionStatus

from .conftest import (
    TEST_API_KEY,
    TEST_BASE_URL,
    TWIN_PLAID,
    TWIN_PROVISION_STATUS,
    TWIN_STRIPE,
)


# --------------------------------------------------------------------------
# Sync tests
# --------------------------------------------------------------------------


class TestListTwins:
    def test_list(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/validate/twins").mock(
            return_value=httpx.Response(200, json=[TWIN_STRIPE, TWIN_PLAID])
        )
        twins = client.twins.list()

        assert len(twins) == 2
        assert all(isinstance(t, Twin) for t in twins)

        stripe = twins[0]
        assert stripe.name == "stripe"
        assert stripe.label == "Stripe Payments"
        assert stripe.kind == "unified"
        assert stripe.show_in_ui is True

        plaid = twins[1]
        assert plaid.name == "plaid"
        assert plaid.label == "Plaid Banking"

    def test_list_empty(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/validate/twins").mock(
            return_value=httpx.Response(200, json=[])
        )
        twins = client.twins.list()
        assert twins == []


class TestProvision:
    def test_provision(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/validate/twins/provision").mock(
            return_value=httpx.Response(
                200, json={"run_id": "run_abc123", "status": "provisioning"}
            )
        )
        result = client.twins.provision(["stripe", "plaid"], ttl_minutes=120)

        assert result == {"run_id": "run_abc123", "status": "provisioning"}

        body = json.loads(route.calls[0].request.content)
        assert body["twins"] == ["stripe", "plaid"]
        assert body["ttl_minutes"] == 120

    def test_provision_with_scenario(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        route = mock_router.post("/validate/twins/provision").mock(
            return_value=httpx.Response(
                200, json={"run_id": "run_abc123", "status": "provisioning"}
            )
        )
        client.twins.provision(
            ["stripe"], ttl_minutes=30, scenario_id="scn_abc123"
        )

        body = json.loads(route.calls[0].request.content)
        assert body["twins"] == ["stripe"]
        assert body["ttl_minutes"] == 30
        assert body["scenario_id"] == "scn_abc123"

    def test_provision_default_ttl(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        route = mock_router.post("/validate/twins/provision").mock(
            return_value=httpx.Response(
                200, json={"run_id": "run_abc123", "status": "provisioning"}
            )
        )
        client.twins.provision(["stripe"])

        body = json.loads(route.calls[0].request.content)
        assert body["ttl_minutes"] == 60  # default


class TestGetStatus:
    def test_get_status(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/validate/twins/provision/run_abc123/status").mock(
            return_value=httpx.Response(200, json=TWIN_PROVISION_STATUS)
        )
        status = client.twins.get_status("run_abc123")

        assert isinstance(status, TwinProvisionStatus)
        assert status.run_id == "run_abc123"
        assert status.status == "ready"
        assert status.dashboard_url == "https://app.argalabs.com/runs/run_abc123"
        assert status.proxy_token == "proxy_tok_abc"
        assert status.expires_at is not None
        assert status.error is None

        # Check nested TwinInstance objects
        assert status.twins is not None
        assert len(status.twins) == 2

        stripe_inst = status.twins["stripe"]
        assert isinstance(stripe_inst, TwinInstance)
        assert stripe_inst.name == "stripe"
        assert stripe_inst.label == "Stripe Payments"
        assert stripe_inst.base_url == "https://twins.argalabs.com/stripe/run_abc123"
        assert stripe_inst.admin_url == "https://twins.argalabs.com/stripe/run_abc123/admin"
        assert stripe_inst.env_vars == {"STRIPE_API_KEY": "sk_test_twin_1234"}
        assert stripe_inst.show_in_ui is True

        plaid_inst = status.twins["plaid"]
        assert isinstance(plaid_inst, TwinInstance)
        assert plaid_inst.name == "plaid"
        assert plaid_inst.admin_url is None


class TestExtend:
    def test_extend(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/validate/twins/provision/run_abc123/extend").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "extended",
                    "expires_at": "2026-03-15T12:30:00Z",
                },
            )
        )
        result = client.twins.extend("run_abc123", ttl_minutes=60)

        assert result["status"] == "extended"
        assert "expires_at" in result

        body = json.loads(route.calls[0].request.content)
        assert body["ttl_minutes"] == 60

    def test_extend_default_ttl(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        route = mock_router.post("/validate/twins/provision/run_abc123/extend").mock(
            return_value=httpx.Response(
                200, json={"status": "extended", "expires_at": "2026-03-15T12:30:00Z"}
            )
        )
        client.twins.extend("run_abc123")

        body = json.loads(route.calls[0].request.content)
        assert body["ttl_minutes"] == 60  # default


# --------------------------------------------------------------------------
# Async tests
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_list_twins(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        router.get("/validate/twins").mock(
            return_value=httpx.Response(200, json=[TWIN_STRIPE, TWIN_PLAID])
        )
        twins = await async_client.twins.list()

        assert len(twins) == 2
        assert twins[0].name == "stripe"
        assert twins[1].name == "plaid"

    await async_client.close()


@pytest.mark.asyncio
async def test_async_get_status(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        router.get("/validate/twins/provision/run_abc123/status").mock(
            return_value=httpx.Response(200, json=TWIN_PROVISION_STATUS)
        )
        status = await async_client.twins.get_status("run_abc123")

        assert isinstance(status, TwinProvisionStatus)
        assert status.status == "ready"
        assert status.twins is not None
        assert "stripe" in status.twins

    await async_client.close()
