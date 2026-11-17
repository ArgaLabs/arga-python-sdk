"""Typed options matching the current public backend request contracts.

Omitted fields stay omitted; explicit None, false, empty collections and strings
are preserved so updates can clear the fields the backend allows clearing.
"""

from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, TypeAdapter
from typing_extensions import TypedDict

Prompt = Annotated[str, Field(min_length=1, max_length=20_000)]
OptionalPrompt = Annotated[str, Field(max_length=20_000)] | None
URL = Annotated[str, Field(max_length=1024)] | None
Repo = Annotated[str, Field(max_length=255)] | None
TTL = Annotated[int, Field(ge=1, le=480)]
GenerationMode = Literal["fast", "thorough"]
Scope = Literal["personal", "workspace"]


class TwinRunOptions(TypedDict, total=False):
    ttl_minutes: TTL
    scenario_id: str | None
    scenario_prompt: str | None
    scenario_generation_mode: GenerationMode
    public: bool
    github_actions_mode: Literal["simulated", "execute"]
    access_profile: Literal["full", "candidate_api_only"]


class TwinRunCreate(TwinRunOptions):
    twins: list[str]


class TwinRunExtend(TypedDict):
    ttl_minutes: TTL


class TestRunOptions(TypedDict, total=False):
    start_url: URL
    sandbox_id: str | None
    test_config: dict[str, Any] | None
    repo: Repo
    branch: Repo
    pr_url: URL
    scenario_id: str | None
    scenario_prompt: OptionalPrompt
    twins: list[str] | None
    ttl_minutes: TTL | None
    trigger_source: Annotated[str, Field(max_length=64)] | None


class TestRunCreate(TestRunOptions):
    prompt: Prompt


class TestRunOverrides(TypedDict, total=False):
    prompt: OptionalPrompt
    start_url: URL
    sandbox_id: str | None
    repo: Repo
    branch: Repo
    pr_url: URL
    scenario_id: str | None
    scenario_prompt: OptionalPrompt
    twins: list[str] | None
    ttl_minutes: TTL | None
    trigger_source: Annotated[str, Field(max_length=64)] | None


class SavedTestRunOptions(TestRunOverrides, total=False):
    session_id: str | None


class SavedTestOptions(TypedDict, total=False):
    description: Annotated[str, Field(max_length=10_000)] | None
    run_id: str | None
    prompt: OptionalPrompt
    start_url: URL
    test_config: dict[str, Any] | None
    repo_full_name: Repo
    ci_enabled: bool
    credentials: dict[str, str] | None
    tags: list[str]


class SavedTestCreate(SavedTestOptions):
    name: Annotated[str, Field(min_length=1, max_length=255)]


class SavedTestUpdate(TypedDict, total=False):
    name: Annotated[str, Field(min_length=1, max_length=255)] | None
    description: Annotated[str, Field(max_length=10_000)] | None
    prompt: OptionalPrompt
    start_url: URL
    test_config: dict[str, Any] | None
    repo_full_name: Repo
    ci_enabled: bool | None
    credentials: dict[str, str] | None
    tags: list[str] | None


class ScenarioUpdateOptions(TypedDict, total=False):
    name: Annotated[str, Field(min_length=1, max_length=80)] | None
    description: str | None
    prompt: str | None
    generation_mode: GenerationMode
    twins: list[str] | None
    seed_config: dict[str, Any] | None
    tags: list[str] | None


_BODIES = (
    TwinRunCreate,
    TwinRunExtend,
    TestRunCreate,
    TestRunOverrides,
    SavedTestRunOptions,
    SavedTestCreate,
    SavedTestUpdate,
    ScenarioUpdateOptions,
)
for _body in _BODIES:
    _body.__pydantic_config__ = ConfigDict(extra="forbid", hide_input_in_errors=True)

_ADAPTERS = {body: TypeAdapter(body) for body in _BODIES}


def request_body(schema: type, fields: dict[str, Any]) -> dict[str, Any]:
    return _ADAPTERS[schema].validate_python(fields)
