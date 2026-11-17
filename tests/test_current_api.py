"""Current public HTTP contracts, including omission/null semantics and sync/async parity."""

import inspect
import json
from importlib.metadata import requires

import httpx
import pytest
from pydantic import ValidationError

from arga_sdk import Arga, ArgaError
from tests.conftest import SCENARIO_RESPONSE

RUN_ID = "00000000-0000-0000-0000-000000000001"
TEST_ID = "00000000-0000-0000-0000-000000000002"
DATASET_ID = "00000000-0000-0000-0000-000000000003"
TASK_ID = "00000000-0000-0000-0000-000000000004"
SCENARIO_ID = "00000000-0000-0000-0000-000000000005"
RUN = {
    "id": RUN_ID,
    "status": "queued",
    "mode": "record_from_prompt",
    "prompt": "Check checkout",
    "start_url": "https://staging.example.org",
    "events_json": [{"id": "event-one", "type": "created"}],
}
TEST = {
    "id": TEST_ID,
    "name": "Checkout",
    "prompt": RUN["prompt"],
    "start_url": RUN["start_url"],
    "test_config_json": {"steps": []},
    "ci_enabled": False,
    "credential_keys": [],
    "has_credentials": False,
}
TWIN = {
    "run_id": RUN_ID,
    "status": "ready",
    "twins": {},
    "access_profile": "candidate_api_only",
    "github_actions_mode": "execute",
    "progress": {"stage": "ready", "timeout_seconds": 900, "elapsed_seconds": 20.5},
}
DATASET = {"id": DATASET_ID, "name": "Support", "source": "sdk", "trace_count": 1}
TASK = {"id": TASK_ID, "trace_id": "a" * 32, "status": "draft", "revision": 2, "spec": {"name": "Support case"}}
ENVIRONMENT = {
    "id": "environment",
    "scenario_id": SCENARIO_ID,
    "status": "queued",
    "requested_twins": ["gmail", "stripe"],
}

# These cases assert wire behavior for every newly exposed REST operation. The
# optional backend-integration suite also runs real backend handlers and models.
CASES = [
    (
        "twin_runs",
        "create",
        (["gmail", "stripe"],),
        {
            "public": False,
            "scenario_generation_mode": "thorough",
            "github_actions_mode": "execute",
            "access_profile": "candidate_api_only",
        },
        "POST",
        "/twin-runs",
        {
            "twins": ["gmail", "stripe"],
            "public": False,
            "scenario_generation_mode": "thorough",
            "github_actions_mode": "execute",
            "access_profile": "candidate_api_only",
        },
        {"run_id": RUN_ID},
    ),
    ("twin_runs", "get", (RUN_ID,), {}, "GET", f"/twin-runs/{RUN_ID}", None, TWIN),
    (
        "twin_runs",
        "extend",
        (RUN_ID,),
        {"ttl_minutes": 45},
        "POST",
        f"/twin-runs/{RUN_ID}/extend",
        {"ttl_minutes": 45},
        {"status": "extended"},
    ),
    (
        "twin_runs",
        "lock",
        (RUN_ID,),
        {},
        "POST",
        f"/twin-runs/{RUN_ID}/lock",
        None,
        {"status": "locked", "is_public": False},
    ),
    ("twin_runs", "teardown", (RUN_ID,), {}, "POST", f"/twin-runs/{RUN_ID}/teardown", None, {"status": "tearing_down"}),
    (
        "twin_runs",
        "reset",
        (RUN_ID,),
        {},
        "POST",
        f"/validate/twins/provision/{RUN_ID}/reset",
        None,
        {"run_id": RUN_ID, "status": "reset_complete"},
    ),
    (
        "twin_runs",
        "microsoft_scenario_snapshot",
        (RUN_ID,),
        {},
        "GET",
        f"/twin-runs/{RUN_ID}/microsoft-scenario-snapshot",
        None,
        {"seed_config": {}},
    ),
    (
        "test_runs",
        "create",
        (RUN["prompt"],),
        {"start_url": RUN["start_url"], "test_config": {}, "ttl_minutes": None},
        "POST",
        "/test-runs",
        {"prompt": RUN["prompt"], "start_url": RUN["start_url"], "test_config": {}, "ttl_minutes": None},
        RUN,
    ),
    ("test_runs", "list", (), {}, "GET", "/test-runs", None, {"runs": [RUN]}),
    ("test_runs", "get", (RUN_ID,), {}, "GET", f"/test-runs/{RUN_ID}", None, RUN),
    (
        "test_runs",
        "rerun",
        (RUN_ID,),
        {"prompt": "Recheck", "twins": []},
        "POST",
        f"/test-runs/{RUN_ID}/rerun",
        {"prompt": "Recheck", "twins": []},
        RUN,
    ),
    (
        "test_runs",
        "update_config",
        (RUN_ID, {"steps": []}),
        {},
        "PATCH",
        f"/test-runs/{RUN_ID}/config",
        {"test_config": {"steps": []}},
        RUN,
    ),
    (
        "test_runs",
        "send_message",
        (RUN_ID, "Inspect the result"),
        {},
        "POST",
        f"/test-runs/{RUN_ID}/messages",
        {"message": "Inspect the result"},
        RUN,
    ),
    (
        "tests",
        "create",
        ("Checkout",),
        {"run_id": RUN_ID, "ci_enabled": False, "tags": []},
        "POST",
        "/tests",
        {"name": "Checkout", "run_id": RUN_ID, "ci_enabled": False, "tags": []},
        TEST,
    ),
    ("tests", "list", (), {}, "GET", "/tests", None, {"tests": [TEST]}),
    ("tests", "get", (TEST_ID,), {}, "GET", f"/tests/{TEST_ID}", None, TEST),
    (
        "tests",
        "update",
        (TEST_ID,),
        {"description": None, "repo_full_name": None, "ci_enabled": False, "tags": [], "credentials": {}},
        "PATCH",
        f"/tests/{TEST_ID}",
        {"description": None, "repo_full_name": None, "ci_enabled": False, "tags": [], "credentials": {}},
        TEST,
    ),
    ("tests", "delete", (TEST_ID,), {}, "DELETE", f"/tests/{TEST_ID}", None, {"status": "deleted"}),
    (
        "tests",
        "run",
        (TEST_ID,),
        {
            "start_url": RUN["start_url"],
            "session_id": "session",
            "repo": "ArgaLabs/example",
            "pr_url": "https://github.com/ArgaLabs/example/pull/1",
        },
        "POST",
        f"/tests/{TEST_ID}/run",
        {
            "start_url": RUN["start_url"],
            "session_id": "session",
            "repo": "ArgaLabs/example",
            "pr_url": "https://github.com/ArgaLabs/example/pull/1",
        },
        RUN,
    ),
    (
        "scenarios",
        "update",
        (SCENARIO_ID,),
        {"description": None, "tags": []},
        "PUT",
        f"/scenarios/{SCENARIO_ID}",
        {"description": None, "tags": []},
        SCENARIO_RESPONSE,
    ),
    ("scenarios", "delete", (SCENARIO_ID,), {}, "DELETE", f"/scenarios/{SCENARIO_ID}", None, {"status": "deleted"}),
    (
        "scenarios",
        "copy",
        (SCENARIO_ID,),
        {"name": "Copy"},
        "POST",
        f"/scenarios/{SCENARIO_ID}/copy",
        {"name": "Copy"},
        SCENARIO_RESPONSE,
    ),
    ("scenarios", "list_presets", (), {}, "GET", "/scenarios/presets", None, [SCENARIO_RESPONSE]),
    (
        "scenarios",
        "get_preset",
        (SCENARIO_ID,),
        {},
        "GET",
        f"/scenarios/presets/{SCENARIO_ID}",
        None,
        SCENARIO_RESPONSE,
    ),
    (
        "scenarios",
        "list_long_runs",
        (),
        {},
        "GET",
        "/scenarios/long-runs",
        None,
        [{"scenario_id": SCENARIO_ID, "run": TWIN}],
    ),
    ("training", "list", (), {}, "GET", "/datasets", None, [DATASET]),
    ("training", "get", (DATASET_ID,), {}, "GET", f"/datasets/{DATASET_ID}", None, {**DATASET, "tasks": [TASK]}),
    (
        "training",
        "generate_task",
        (DATASET_ID,),
        {"trace_id": "a" * 32},
        "POST",
        f"/datasets/{DATASET_ID}/tasks",
        {"trace_id": "a" * 32, "variation": ""},
        TASK,
    ),
    (
        "training",
        "update_task",
        (DATASET_ID, TASK_ID),
        {"revision": 2, "spec": {"name": "Updated"}},
        "PUT",
        f"/datasets/{DATASET_ID}/tasks/{TASK_ID}",
        {"revision": 2, "spec": {"name": "Updated"}},
        TASK,
    ),
    (
        "training",
        "review_task",
        (DATASET_ID, TASK_ID),
        {"revision": 2, "decision": "approved", "acknowledge_assumptions": True, "acknowledge_grader": True},
        "POST",
        f"/datasets/{DATASET_ID}/tasks/{TASK_ID}/review",
        {"revision": 2, "decision": "approved", "acknowledge_assumptions": True, "acknowledge_grader": True},
        TASK,
    ),
    (
        "training",
        "prepare_grader",
        (DATASET_ID, TASK_ID),
        {"revision": 2},
        "POST",
        f"/datasets/{DATASET_ID}/tasks/{TASK_ID}/grader",
        {"revision": 2},
        TASK,
    ),
    (
        "training",
        "get_grader",
        (DATASET_ID, TASK_ID),
        {},
        "GET",
        f"/datasets/{DATASET_ID}/tasks/{TASK_ID}/grader",
        None,
        {"revision": 2, "grader": {"source": "code"}},
    ),
    (
        "training",
        "test_grader",
        (DATASET_ID, TASK_ID),
        {"revision": 2, "before": {}, "after": {}},
        "POST",
        f"/datasets/{DATASET_ID}/tasks/{TASK_ID}/grader/test",
        {"revision": 2, "before": {}, "after": {}},
        {"outcome": "error", "score": None},
    ),
    (
        "training",
        "create_environment",
        (DATASET_ID, TASK_ID),
        {},
        "POST",
        f"/datasets/{DATASET_ID}/tasks/{TASK_ID}/environment",
        None,
        ENVIRONMENT,
    ),
]


async def invoke(target, method, *args, **kwargs):
    result = getattr(target, method)(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(
    "namespace,method,args,kwargs,verb,path,body,response", CASES, ids=[f"{row[0]}.{row[1]}" for row in CASES]
)
async def test_current_http_contracts(
    client, async_client, mock_router, asynchronous, namespace, method, args, kwargs, verb, path, body, response
):
    route = mock_router.request(verb, path).mock(return_value=httpx.Response(200, json=response))
    sdk = async_client if asynchronous else client
    result = await invoke(getattr(sdk, namespace), method, *args, **kwargs)
    assert result is not None and route.call_count == 1
    request = route.calls[0].request
    if body is not None:
        assert json.loads(request.content) == body
    else:
        assert not request.content or json.loads(request.content) is None
    if namespace == "test_runs" and method == "list":
        assert result[0].id == RUN_ID and result[0].events_json[0]["id"] == "event-one"
    if namespace == "twin_runs" and method == "get":
        assert result.progress.timeout_seconds == 900 and result.access_profile == "candidate_api_only"
    if namespace == "tests" and method == "list":
        assert result[0].id == TEST_ID and result[0].test_config_json == TEST["test_config_json"]
    if namespace == "training" and method == "get":
        assert result.tasks[0].revision == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_nullable_updates_omit_unset_fields(client, async_client, mock_router, asynchronous):
    route = mock_router.patch(f"/tests/{TEST_ID}").mock(return_value=httpx.Response(200, json=TEST))
    sdk = async_client if asynchronous else client
    await invoke(sdk.tests, "update", TEST_ID, name="Renamed")
    assert json.loads(route.calls[0].request.content) == {"name": "Renamed"}


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_current_filters_and_workspace_scope(client, async_client, mock_router, asynchronous):
    sdk = async_client if asynchronous else client
    listing = mock_router.get("/scenarios").mock(return_value=httpx.Response(200, json=[SCENARIO_RESPONSE]))
    await invoke(sdk.scenarios, "list", scope="workspace", include_presets=False, limit=10, offset=0, search="billing")
    assert dict(listing.calls[0].request.url.params) == {
        "scope": "workspace",
        "include_presets": "false",
        "limit": "10",
        "offset": "0",
        "search": "billing",
    }
    create = mock_router.post("/scenarios").mock(
        return_value=httpx.Response(200, json={**SCENARIO_RESPONSE, "scope": "workspace"})
    )
    created = await invoke(sdk.scenarios, "create", "Billing", prompt="Billing records", scope="workspace")
    assert created.scope == "workspace" and json.loads(create.calls[0].request.content)["scope"] == "workspace"
    saved = mock_router.get("/tests").mock(return_value=httpx.Response(200, json={"tests": []}))
    await invoke(sdk.tests, "list", repo_full_name="ArgaLabs/example")
    assert saved.calls[0].request.url.params["repo_full_name"] == "ArgaLabs/example"


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_artifact_redirect_does_not_forward_credentials(client, async_client, mock_router, asynchronous):
    signed = "https://storage.googleapis.com/example/artifact.png?signature=private"
    route = mock_router.get(f"/test-runs/{RUN_ID}/artifacts/screenshots/first step.png").mock(
        return_value=httpx.Response(307, headers={"Location": signed})
    )
    sdk = async_client if asynchronous else client
    assert await invoke(sdk.test_runs, "artifact_url", RUN_ID, "screenshots/first step.png") == signed
    assert b"first%20step.png" in route.calls[0].request.url.raw_path
    with pytest.raises(ValueError):
        await invoke(sdk.test_runs, "artifact_url", RUN_ID, "../another-run/secret")


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_training_export_preserves_jsonl(client, async_client, mock_router, asynchronous):
    text = '{"task_id":"one"}\n{"task_id":"two"}\n'
    mock_router.get(f"/datasets/{DATASET_ID}/export").mock(
        return_value=httpx.Response(200, text=text, headers={"Content-Type": "application/x-ndjson"})
    )
    sdk = async_client if asynchronous else client
    assert await invoke(sdk.training, "export_jsonl", DATASET_ID) == text


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_polling_ready_failed_and_timeout(client, async_client, mock_router, asynchronous):
    sdk = async_client if asynchronous else client
    route = mock_router.get(f"/twin-runs/{RUN_ID}")
    route.side_effect = [httpx.Response(200, json={**TWIN, "status": "provisioning"}), httpx.Response(200, json=TWIN)]
    assert (await invoke(sdk.twin_runs, "wait", RUN_ID, poll_interval=0.001, timeout=1)).status == "ready"
    test = mock_router.get(f"/test-runs/{RUN_ID}")
    test.return_value = httpx.Response(
        200, json={**RUN, "status": "failed", "error_message": "Browser assertion failed"}
    )
    assert (await invoke(sdk.test_runs, "wait", RUN_ID, poll_interval=0.001, timeout=1)).status == "failed"
    test.return_value = httpx.Response(200, json=RUN)
    with pytest.raises(ArgaError, match="Timed out"):
        await invoke(sdk.test_runs, "wait", RUN_ID, poll_interval=0.001, timeout=0.005)


def test_unknown_and_invalid_options_fail_before_sending(client, mock_router):
    with pytest.raises(ValidationError):
        client.test_runs.create("Check checkout", credentials={"password": "never-upload"})
    with pytest.raises(ValidationError):
        client.tests.create("Checkout", made_up="value")
    with pytest.raises(ValidationError):
        client.twin_runs.create(["stripe"], ttl_minutes=0)
    with pytest.raises(ValidationError):
        client.test_runs.rerun(RUN_ID, test_config={})
    assert not mock_router.calls


def test_standard_install_includes_tracing_dependencies_and_uses_api_host():
    dependencies = requires("arga-py-sdk")
    for name in ["stripe", "google-api-python-client"]:
        requirement = next(item for item in dependencies if item.startswith(name))
        assert "extra ==" not in requirement
    with Arga(api_key="test") as sdk:
        assert str(sdk._http._client.base_url) == "https://api.argalabs.com"
