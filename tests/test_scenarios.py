from __future__ import annotations

import json

import httpx
import pytest
import respx

from arga_sdk import Arga, AsyncArga, Scenario

from .conftest import (
    SCENARIO_RESPONSE,
    TEST_BASE_URL,
)


# --------------------------------------------------------------------------
# Sync tests
# --------------------------------------------------------------------------


class TestCreateScenario:
    def test_create_basic(self, client: Arga, mock_router: respx.Router) -> None:
        route = mock_router.post("/scenarios").mock(
            return_value=httpx.Response(200, json=SCENARIO_RESPONSE)
        )
        scenario = client.scenarios.create("Login Flow Test")

        assert isinstance(scenario, Scenario)
        assert scenario.id == "scn_abc123"
        assert scenario.name == "Login Flow Test"
        assert scenario.description == "Validates the login flow end-to-end"
        assert scenario.prompt == "Test the login form with valid and invalid credentials"
        assert scenario.twins == ["stripe"]
        assert scenario.seed_config == {
            "users": [{"email": "test@example.com", "password": "secret"}]
        }
        assert scenario.tags == ["auth", "login"]
        assert scenario.created_at is not None
        assert scenario.updated_at is not None

        body = json.loads(route.calls[0].request.content)
        assert body == {"name": "Login Flow Test"}

    def test_create_with_all_options(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        route = mock_router.post("/scenarios").mock(
            return_value=httpx.Response(200, json=SCENARIO_RESPONSE)
        )
        client.scenarios.create(
            "Login Flow Test",
            prompt="Test the login form",
            seed_config={"users": [{"email": "a@b.com"}]},
            twins=["stripe"],
            description="E2E login test",
            tags=["auth"],
        )

        body = json.loads(route.calls[0].request.content)
        assert body["name"] == "Login Flow Test"
        assert body["prompt"] == "Test the login form"
        assert body["seed_config"] == {"users": [{"email": "a@b.com"}]}
        assert body["twins"] == ["stripe"]
        assert body["description"] == "E2E login test"
        assert body["tags"] == ["auth"]


class TestListScenarios:
    def test_list_all(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/scenarios").mock(
            return_value=httpx.Response(200, json=[SCENARIO_RESPONSE])
        )
        scenarios = client.scenarios.list()

        assert len(scenarios) == 1
        assert isinstance(scenarios[0], Scenario)
        assert scenarios[0].id == "scn_abc123"

    def test_list_with_twin_filter(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        route = mock_router.get("/scenarios").mock(
            return_value=httpx.Response(200, json=[SCENARIO_RESPONSE])
        )
        client.scenarios.list(twin="stripe")

        request = route.calls[0].request
        assert "twin=stripe" in str(request.url)

    def test_list_with_tag_filter(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        route = mock_router.get("/scenarios").mock(
            return_value=httpx.Response(200, json=[SCENARIO_RESPONSE])
        )
        client.scenarios.list(tag="auth")

        request = route.calls[0].request
        assert "tag=auth" in str(request.url)

    def test_list_with_both_filters(
        self, client: Arga, mock_router: respx.Router
    ) -> None:
        route = mock_router.get("/scenarios").mock(
            return_value=httpx.Response(200, json=[SCENARIO_RESPONSE])
        )
        client.scenarios.list(twin="stripe", tag="auth")

        request = route.calls[0].request
        url_str = str(request.url)
        assert "twin=stripe" in url_str
        assert "tag=auth" in url_str

    def test_list_empty(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/scenarios").mock(
            return_value=httpx.Response(200, json=[])
        )
        scenarios = client.scenarios.list()
        assert scenarios == []


class TestGetScenario:
    def test_get(self, client: Arga, mock_router: respx.Router) -> None:
        mock_router.get("/scenarios/scn_abc123").mock(
            return_value=httpx.Response(200, json=SCENARIO_RESPONSE)
        )
        scenario = client.scenarios.get("scn_abc123")

        assert isinstance(scenario, Scenario)
        assert scenario.id == "scn_abc123"
        assert scenario.name == "Login Flow Test"


# --------------------------------------------------------------------------
# Async tests
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_create_scenario(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        route = router.post("/scenarios").mock(
            return_value=httpx.Response(200, json=SCENARIO_RESPONSE)
        )
        scenario = await async_client.scenarios.create(
            "Login Flow Test", prompt="Test login"
        )

        assert isinstance(scenario, Scenario)
        assert scenario.id == "scn_abc123"

        body = json.loads(route.calls[0].request.content)
        assert body["name"] == "Login Flow Test"
        assert body["prompt"] == "Test login"

    await async_client.close()


@pytest.mark.asyncio
async def test_async_list_scenarios(async_client: AsyncArga) -> None:
    with respx.mock(base_url=TEST_BASE_URL) as router:
        router.get("/scenarios").mock(
            return_value=httpx.Response(200, json=[SCENARIO_RESPONSE])
        )
        scenarios = await async_client.scenarios.list(twin="stripe")

        assert len(scenarios) == 1
        assert scenarios[0].name == "Login Flow Test"

    await async_client.close()
