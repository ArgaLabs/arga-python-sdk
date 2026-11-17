from __future__ import annotations

import importlib
import sys
from pathlib import Path

import httpx
import pytest
import respx

from tests.conftest import TEST_BASE_URL

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
MODULE_NAMES = [
    "validate_staging_release",
    "create_checkout_scenario",
    "ensure_scenario_twin_urls",
    "provision_checkout_twins",
    "explore_staging_with_agent",
]


def test_examples_import_without_running() -> None:
    sys.path.insert(0, str(EXAMPLES_DIR))
    try:
        for module_name in MODULE_NAMES:
            module = importlib.import_module(module_name)
            assert hasattr(module, "main")
    finally:
        if str(EXAMPLES_DIR) in sys.path:
            sys.path.remove(str(EXAMPLES_DIR))

        for module_name in MODULE_NAMES + ["_shared"]:
            sys.modules.pop(module_name, None)


@pytest.mark.parametrize(
    "module_name", ["validate_staging_release", "explore_staging_with_agent", "provision_checkout_twins"]
)
def test_current_examples_run_against_canonical_api_contracts(module_name, monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES_DIR))
    monkeypatch.setenv("ARGA_API_KEY", "example-test-key")
    monkeypatch.setenv("ARGA_BASE_URL", TEST_BASE_URL)
    monkeypatch.setenv("STAGING_URL", "https://staging.example.test")
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    with respx.mock(base_url=TEST_BASE_URL) as router:
        if module_name == "provision_checkout_twins":
            router.post("/twin-runs").mock(return_value=httpx.Response(200, json={"run_id": "run-id"}))
            router.get("/twin-runs/run-id").mock(
                return_value=httpx.Response(200, json={"run_id": "run-id", "status": "ready", "twins": {}})
            )
        else:
            run = {
                "id": "run-id",
                "status": "completed",
                "mode": "record_from_prompt",
                "prompt": "Check checkout",
                "start_url": "https://staging.example.test",
            }
            router.post("/test-runs").mock(return_value=httpx.Response(200, json={**run, "status": "queued"}))
            router.get("/test-runs/run-id").mock(return_value=httpx.Response(200, json=run))
        module.main()
    sys.modules.pop(module_name, None)
