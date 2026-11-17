"""Optional tests against an actual backend checkout, without cloud/provider operations.

Run in the backend's dev environment with this SDK's src directory on PYTHONPATH
and ARGA_BACKEND_CHECKOUT pointing at the checkout (including companion PR #2987
for evidence ingestion). Ordinary SDK CI runs the independent wire-contract suite.
"""

# Backend imports intentionally follow the optional skip and checkout selection.
# ruff: noqa: E402

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import get_args

import httpx
import pytest
import pytest_asyncio
from pydantic import TypeAdapter

BACKEND = os.environ.get("ARGA_BACKEND_CHECKOUT")
if not BACKEND:
    pytest.skip("Set ARGA_BACKEND_CHECKOUT for real backend contract tests", allow_module_level=True)
sys.path.insert(0, BACKEND)

from app.api import (
    routes_datasets,
    routes_run_model,
    routes_runner,
    routes_scenarios,
    routes_validate,
)
from app.auth.middleware import (
    get_current_user_or_api_key,
    get_current_user_or_full_api_key,
)
from app.db.database import get_db
from app.db.models import (
    RunnerRun,
    RunnerTest,
    Scenario,
    TraceDataset,
    TrainingTask,
    User,
)
from app.training.evidence_auth import evidence_identity
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from arga_sdk import ArgaAPIError, AsyncArga, options, types
from arga_sdk.tracing import Episode


def test_request_and_response_fields_match_current_backend():
    request_pairs = [
        (options.TwinRunCreate, routes_validate.TwinProvisionRequest),
        (options.TwinRunExtend, routes_validate.TwinExtendRequest),
        (options.TestRunCreate, routes_runner.RunnerRunCreateRequest),
        (options.TestRunOverrides, routes_runner.RunnerRunRerunRequest),
        (options.SavedTestCreate, routes_runner.RunnerTestCreateRequest),
        (options.SavedTestUpdate, routes_runner.RunnerTestUpdateRequest),
        (options.SavedTestRunOptions, routes_runner.RunnerTestRunRequest),
        (options.ScenarioUpdateOptions, routes_scenarios.ScenarioUpdate),
    ]
    for sdk, backend in request_pairs:
        assert set(TypeAdapter(sdk).json_schema()["properties"]) == set(backend.model_fields), sdk.__name__
    for sdk, backend in [
        (types.TestRun, routes_runner.RunnerRunResponse),
        (types.SavedTest, routes_runner.RunnerTestResponse),
        (types.TwinProvisionStatus, routes_validate.TwinProvisionStatusResponse),
        (types.Scenario, routes_scenarios.ScenarioResponse),
        (types.ScenarioTwinEnvironment, routes_scenarios.ScenarioTwinEnvironmentResponse),
    ]:
        assert set(backend.model_fields) <= set(sdk.model_fields), sdk.__name__


@pytest_asyncio.fixture
async def backend_sdk(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        for model in (User, RunnerRun, RunnerTest, Scenario, TraceDataset, TrainingTask):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        user = User(
            id=uuid.uuid4(),
            api_key="sdk-contract-key",
            email="sdk-contract@example.invalid",
            email_verified_at=datetime.now(timezone.utc),
        )
        scenario = Scenario(
            user_id=user.id,
            name="Empty Stripe",
            scope="personal",
            twins=["stripe"],
            seed_config={"stripe": {"support": {"customers": [], "payments": [], "refunds": []}}},
            tags=[],
        )
        db.add_all([user, scenario])
        await db.commit()
    app = FastAPI()
    app.include_router(routes_run_model.router)
    app.include_router(routes_scenarios.router)
    app.include_router(routes_datasets.router)

    async def database():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user_or_full_api_key] = lambda: user
    app.dependency_overrides[get_current_user_or_api_key] = lambda: user
    app.dependency_overrides[evidence_identity] = lambda: (user, None)
    launches = []

    async def launch(run, db):
        launches.append(str(run.id))  # No hosted agent, provider requests or GCP jobs.

    monkeypatch.setattr(routes_runner, "_launch_test_runner", launch)
    sdk = AsyncArga(api_key="sdk-contract-key", base_url="https://backend.example.test")
    await sdk._http._client.aclose()
    sdk._http._client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://backend.example.test"
    )
    try:
        yield sdk, str(scenario.id), launches
    finally:
        await sdk.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_record_save_update_and_rerun_with_actual_backend(backend_sdk):
    sdk, _, launches = backend_sdk
    run = await sdk.test_runs.create(
        "Check checkout", start_url="https://staging.example.org", repo="ArgaLabs/example", twins=["stripe"]
    )
    assert run.status == "queued" and run.id in launches
    assert run.artifacts_json["repo_full_name"] == "ArgaLabs/example"
    config = {"steps": [{"id": "first", "action": "goto", "value": run.start_url}]}
    updated = await sdk.test_runs.update_config(run.id, config)
    assert updated.test_config_json == config
    saved = await sdk.tests.create(
        "Checkout", run_id=run.id, repo_full_name="ArgaLabs/example", ci_enabled=True, description="Old description"
    )
    assert saved.source_run_id == run.id and saved.test_config_json == config
    assert len(await sdk.tests.list(repo_full_name="ArgaLabs/example")) == 1
    changed = await sdk.tests.update(
        saved.id, description=None, repo_full_name=None, ci_enabled=False, credentials={}, tags=[]
    )
    assert changed.description is None and changed.repo_full_name is None and not changed.ci_enabled
    rerun = await sdk.tests.run(saved.id, start_url="https://preview.example.org", session_id="saved-test-session")
    assert rerun.id != run.id and rerun.mode == "rerun_from_config"
    assert rerun.test_config_json["steps"][0]["value"] == "https://preview.example.org"
    again = await sdk.test_runs.rerun(run.id, prompt="Recheck checkout")
    assert again.source_run_id == run.id and again.prompt == "Recheck checkout"
    messaged = await sdk.test_runs.send_message(again.id, "Inspect final state")
    assert messaged.events_json[-1]["message"] == "Inspect final state"
    assert (await sdk.test_runs.get(again.id)).id == again.id
    assert len(await sdk.test_runs.list()) == 3
    await sdk.tests.delete(saved.id)
    with pytest.raises(ArgaAPIError) as error:
        await sdk.tests.get(saved.id)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_scenarios_catalog_and_filtered_evidence_use_actual_backend(backend_sdk):
    sdk, scenario_id, _ = backend_sdk
    catalog = await sdk.twins.list()
    assert {twin.name for twin in catalog} <= set(get_args(types.KnownTwinName))
    scenario = await sdk.scenarios.get(scenario_id)
    assert scenario.permissions.can_edit and scenario.scope == "personal"
    updated = await sdk.scenarios.update(scenario_id, description=None, tags=[])
    assert updated.description is None
    copied = await sdk.scenarios.copy(scenario_id, name="Private copy")
    assert copied.id != scenario_id and copied.seed_config == scenario.seed_config
    found = await sdk.scenarios.list(limit=1, offset=0, search="Private copy", scope="personal")
    assert [item.id for item in found] == [copied.id]
    await sdk.scenarios.delete(copied.id)
    evidence = Episode.model_validate(
        json.loads((Path(__file__).parent / "fixtures/support-evidence-v1.json").read_text())
    )
    imported = await sdk.training.upload_evidence(evidence)
    retained = await sdk.training.get(imported["id"])
    assert retained.traces[0]["id"] == evidence.episode_id
    assert retained.source == "sdk" and len(await sdk.training.list()) == 1
    assert (await sdk.training.upload_evidence(evidence))["id"] == retained.id
    with pytest.raises(ArgaAPIError) as error:
        await sdk.training.export_jsonl(retained.id)
    assert error.value.status_code == 409  # Approval remains mandatory.
