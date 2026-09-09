from __future__ import annotations

import json
from typing import get_args

import httpx
import pytest

from arga_sdk import ScenarioGenerationMode

from .conftest import SCENARIO_RESPONSE


def test_public_mode_type():
    assert get_args(ScenarioGenerationMode) == ("fast", "thorough")


@pytest.mark.parametrize("mode", [None, "fast", "thorough"])
@pytest.mark.parametrize("resource", ["scenarios", "twins"])
def test_sync_generation_modes(client, mock_router, mode, resource):
    path = "/scenarios" if resource == "scenarios" else "/validate/twins/provision"
    response = SCENARIO_RESPONSE if resource == "scenarios" else {"run_id": "run-1"}
    route = mock_router.post(path).mock(return_value=httpx.Response(200, json=response))
    if resource == "scenarios":
        kwargs = {"name": "Example", "prompt": "A Slack support channel"}
        if mode:
            kwargs["generation_mode"] = mode
        client.scenarios.create(**kwargs)
    else:
        kwargs = {"twins": ["slack"], "scenario_prompt": "A support channel", "ttl_minutes": 60}
        if mode:
            kwargs["scenario_generation_mode"] = mode
        client.twins.provision(**kwargs)
    assert json.loads(route.calls.last.request.content) == kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [None, "fast", "thorough"])
@pytest.mark.parametrize("resource", ["scenarios", "twins"])
async def test_async_generation_modes(async_client, mock_router, mode, resource):
    path = "/scenarios" if resource == "scenarios" else "/validate/twins/provision"
    response = SCENARIO_RESPONSE if resource == "scenarios" else {"run_id": "run-1"}
    route = mock_router.post(path).mock(return_value=httpx.Response(200, json=response))
    try:
        if resource == "scenarios":
            kwargs = {"name": "Example", "prompt": "A Slack support channel"}
            if mode:
                kwargs["generation_mode"] = mode
            await async_client.scenarios.create(**kwargs)
        else:
            kwargs = {"twins": ["slack"], "scenario_prompt": "A support channel", "ttl_minutes": 60}
            if mode:
                kwargs["scenario_generation_mode"] = mode
            await async_client.twins.provision(**kwargs)
        assert json.loads(route.calls.last.request.content) == kwargs
    finally:
        await async_client.close()
