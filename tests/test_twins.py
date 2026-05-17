from __future__ import annotations

import json
from typing import get_args

import httpx
import pytest
import respx

from arga_sdk import (
    Arga,
    AsyncArga,
    KnownTwinName,
    Twin,
    TwinInstance,
    TwinProvisionStatus,
    TwinResetResult,
)

from .conftest import (
    TEST_API_KEY,
    TEST_BASE_URL,
    TWIN_PLAID,
    TWIN_PROVISION_STATUS,
    TWIN_PUBLIC_PROVISION_STATUS,
    TWIN_SALESFORCE,
    TWIN_SALESFORCE_PROVISION_STATUS,
    TWIN_STRIPE,
)


# --------------------------------------------------------------------------
# Sync tests
# --------------------------------------------------------------------------


class TestListTwins:
    def test_known_twin_names_include_salesforce(self) -> None:
        assert "salesforce" in get_args(KnownTwinName)

    def test_known_twin_names_include_linkedin(self) -> None:
        assert "linkedin" in get_args(KnownTwinName)

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
        assert plaid.name == "slack"
        assert plaid.label == "Slack"
        assert plaid.mcp is not None
        assert plaid.mcp["path"] == "/mcp"

    def test_list_includes_salesforce(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/validate/twins").mock(return_value=httpx.Response(200, json=[TWIN_SALESFORCE]))
        twins = client.twins.list()

        assert len(twins) == 1
        assert twins[0].name == "salesforce"
        assert twins[0].label == "Salesforce"
        assert twins[0].kind == "backend"

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
        # Don't send `public` unless the caller explicitly asks — keeps the
        # server-side default authoritative, so we don't force SDK releases
        # whenever that policy shifts.
        assert "public" not in body

    def test_provision_with_public_false(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        """Callers can force a private, proxy-auth-gated environment."""
        route = mock_router.post("/validate/twins/provision").mock(
            return_value=httpx.Response(
                200, json={"run_id": "run_abc123", "status": "provisioning"}
            )
        )
        client.twins.provision(["stripe"], public=False)

        body = json.loads(route.calls[0].request.content)
        assert body["public"] is False

    def test_provision_with_public_true(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        """Callers can explicitly opt in to the drop-in ``pub-`` experience."""
        route = mock_router.post("/validate/twins/provision").mock(
            return_value=httpx.Response(
                200, json={"run_id": "run_abc123", "status": "provisioning"}
            )
        )
        client.twins.provision(["stripe"], public=True)

        body = json.loads(route.calls[0].request.content)
        assert body["public"] is True

    def test_provision_salesforce(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/validate/twins/provision").mock(
            return_value=httpx.Response(200, json={"run_id": "run_sf123", "status": "provisioning"})
        )
        client.twins.provision(["salesforce"], ttl_minutes=45)

        body = json.loads(route.calls[0].request.content)
        assert body["twins"] == ["salesforce"]
        assert body["ttl_minutes"] == 45


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

        assert status.is_public is False

    def test_get_status_public_run(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        """Public runs surface ``is_public=True`` so callers know ``base_url``
        is directly usable from a native SDK. ``proxy_token`` is still
        returned for admin-side operations (CLI reset, dashboard cookies)
        that hit the private ``admin_url``."""
        mock_router.get("/validate/twins/provision/run_pub123/status").mock(
            return_value=httpx.Response(200, json=TWIN_PUBLIC_PROVISION_STATUS)
        )
        status = client.twins.get_status("run_pub123")

        assert status.is_public is True
        assert status.proxy_token == "proxy_tok_pub"
        assert status.twins is not None
        slack_inst = status.twins["slack"]
        assert slack_inst.base_url is not None
        assert slack_inst.base_url.startswith("https://pub-r")
        # The admin_url keeps the private host so the dashboard's cookie/JWT
        # path still works and doesn't inherit public access.
        assert slack_inst.admin_url is not None
        assert slack_inst.admin_url.startswith("https://r")
        assert not slack_inst.admin_url.startswith("https://pub-r")
        assert slack_inst.mcp_url is not None
        assert slack_inst.mcp_url.endswith("/mcp")
        assert slack_inst.mcp is not None
        assert slack_inst.mcp["path"] == "/mcp"

    def test_get_status_salesforce_env_vars(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/validate/twins/provision/run_sf123/status").mock(
            return_value=httpx.Response(200, json=TWIN_SALESFORCE_PROVISION_STATUS)
        )
        status = client.twins.get_status("run_sf123")

        assert status.is_public is True
        assert status.twins is not None
        salesforce = status.twins["salesforce"]
        assert isinstance(salesforce, TwinInstance)
        assert salesforce.base_url is not None
        assert salesforce.base_url.startswith("https://pub-r")
        assert salesforce.env_vars == {
            "SALESFORCE_ACCESS_TOKEN": "00D000000000001!salesforce-twin-token",
            "SALESFORCE_INSTANCE_URL": salesforce.base_url,
            "SALESFORCE_API_BASE_URL": salesforce.base_url,
        }


class TestReset:
    def test_reset(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.post("/validate/twins/provision/run_abc123/reset").mock(
            return_value=httpx.Response(
                200,
                json={
                    "run_id": "run_abc123",
                    "status": "reset_complete",
                    "baseline_kind": "scenario",
                    "factory_reset": {"slack": {"status": "ok"}},
                    "seed_results": {"slack": {"status": "seeded"}},
                },
            )
        )
        result = client.twins.reset("run_abc123")
        assert isinstance(result, TwinResetResult)
        assert result.run_id == "run_abc123"
        assert result.status == "reset_complete"
        assert result.baseline_kind == "scenario"
        assert result.factory_reset["slack"]["status"] == "ok"


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
        assert twins[1].name == "slack"
        assert twins[1].mcp is not None
        assert twins[1].mcp["path"] == "/mcp"

    await async_client.close()


@pytest.mark.asyncio
async def test_async_reset(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        router.post("/validate/twins/provision/run_abc123/reset").mock(
            return_value=httpx.Response(
                200,
                json={
                    "run_id": "run_abc123",
                    "status": "reset_complete",
                    "baseline_kind": "empty",
                    "factory_reset": {},
                    "seed_results": {},
                },
            )
        )
        result = await async_client.twins.reset("run_abc123")
        assert isinstance(result, TwinResetResult)
        assert result.status == "reset_complete"

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
