from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

ScenarioGenerationMode: TypeAlias = Literal["fast", "thorough"]
"""Fast favors speed; thorough handles complex requirements with a longer wait."""

KnownTwinName: TypeAlias = Literal[
    "asana",
    "atlassian",
    "attio",
    "auth0",
    "bivo",
    "box",
    "checkhq",
    "datadog",
    "discord",
    "documenso",
    "dropbox",
    "excel",
    "github",
    "github_actions",
    "gitlab",
    "gmail",
    "gong",
    "google_calendar",
    "google_docs",
    "google_drive",
    "google_sheets",
    "google_slides",
    "google_workspace",
    "hubspot",
    "jira",
    "kandji",
    "linear",
    "linkedin",
    "loops",
    "middesk",
    "microsoft",
    "mindtickle",
    "netsuite",
    "notion",
    "okta",
    "onedrive",
    "postgres",
    "powerpoint",
    "quickbooks",
    "ramp",
    "resend",
    "salesforce",
    "seismic",
    "serval",
    "slack",
    "stripe",
    "supabase",
    "symmetry_i9",
    "thatch",
    "trolley",
    "twilio",
    "unified",
    "unstructured",
    "waterfall",
    "word",
    "xero",
]


class Run(BaseModel):
    """Response from creating a run."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    status: str
    session_id: str | None = None


class RunDetail(BaseModel):
    """Full run details returned by GET /runs/{run_id}."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    run_id: str | None = None
    status: str
    run_type: str | None = None
    mode: str | None = None
    environment_url: str | None = None
    surface_urls: list[str] | None = None
    twins: list[str] | None = None
    results_json: Any | None = None
    event_log_json: Any | None = None
    story_json: Any | None = None
    attack_plan_json: Any | None = None
    redteam_report_json: Any | None = None
    step_summaries: Any | None = None
    failure_category: str | None = None
    failure_detail: str | dict[str, Any] | None = None
    created_at: datetime | None = None


class Twin(BaseModel):
    """A service twin definition."""

    model_config = ConfigDict(extra="allow")

    name: str
    label: str | None = None
    kind: str | None = None
    show_in_ui: bool | None = None
    mcp: dict[str, Any] | None = None


class TwinInstance(BaseModel):
    """A provisioned twin instance."""

    model_config = ConfigDict(extra="allow")

    name: str
    label: str | None = None
    base_url: str | None = None
    admin_url: str | None = None
    env_vars: dict[str, str] | None = None
    show_in_ui: bool | None = None
    mcp_url: str | None = None
    mcp: dict[str, Any] | None = None


class TwinResetResult(BaseModel):
    """Result of resetting quickstart twins to their captured baseline seed state."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    status: str
    baseline_kind: str | None = None
    factory_reset: dict[str, Any] = Field(default_factory=dict)
    seed_results: dict[str, Any] = Field(default_factory=dict)


class TwinProvisionStatus(BaseModel):
    """Status of a twin provisioning request."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    status: str
    twins: dict[str, TwinInstance] | None = None
    dashboard_url: str | None = None
    expires_at: datetime | None = None
    # Proxy token for hitting each twin's ``admin_url`` (and, for private
    # runs, its ``base_url``). Always returned once a run is ready; for
    # public runs the ``base_url`` is directly callable without it, but
    # admin-side ops still need it.
    proxy_token: str | None = None
    # True when the run's ``base_url``s are the drop-in ``pub-r<id>...``
    # hosts. Lets callers distinguish "drop-in ready" from "needs proxy_token
    # wired through the HTTP client".
    is_public: bool | None = None
    error: str | None = None
    failure_category: str | None = None
    failure_detail: TwinProvisionFailure | None = None
    progress: TwinProvisionProgress | None = None
    seed_results: dict[str, Any] | None = None
    github_actions_mode: Literal["simulated", "execute"] = "simulated"
    access_profile: Literal["full", "candidate_api_only"] = "full"


class ScenarioTwinEnvironment(BaseModel):
    """Long-lived twin environment pinned to a scenario."""

    model_config = ConfigDict(extra="allow")

    id: str
    scenario_id: str
    status: str
    requested_twins: list[str]
    twins: dict[str, TwinInstance] | None = None
    run_id: str | None = None
    dashboard_url: str | None = None
    proxy_token: str | None = None
    public: bool = True
    github_actions_mode: Literal["simulated", "execute"] = "simulated"
    error: str | None = None
    seed_results: dict[str, Any] | None = None
    last_seeded_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Scenario(BaseModel):
    """A test scenario."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str | None = None
    prompt: str | None = None
    twins: list[str] | None = None
    seed_config: dict[str, Any] | None = None
    tags: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    scope: Literal["personal", "workspace"] = "personal"
    workspace_id: str | None = None
    created_by_user_id: str | None = None
    is_preset: bool = False
    permissions: ScenarioPermissions = Field(default_factory=lambda: ScenarioPermissions())


class TwinProvisionFailure(BaseModel):
    model_config = ConfigDict(extra="allow")
    phase: str
    kind: str
    code: str
    public_message: str
    retryable: bool


class TwinProvisionProgress(BaseModel):
    model_config = ConfigDict(extra="allow")
    stage: str
    timeout_seconds: int
    stage_started_at: datetime | None = None
    elapsed_seconds: float | None = None
    stage_elapsed_seconds: float | None = None
    stalled: bool = False


class ScenarioPermissions(BaseModel):
    can_edit: bool = False
    can_delete: bool = False
    can_clone: bool = False
    can_create_environment: bool = False


class TwinRun(BaseModel):
    """Accepted Twin Run; poll twin_runs.get/wait for endpoints and progress."""

    model_config = ConfigDict(extra="allow")
    run_id: str
    status: str | None = None
    session_id: str | None = None


class TestRun(BaseModel):
    """Browser Test Run returned by the canonical /test-runs API."""

    model_config = ConfigDict(extra="allow")
    id: str
    status: str
    mode: str
    prompt: str
    start_url: str
    source_run_id: str | None = None
    sandbox_id: str | None = None
    test_config_json: dict[str, Any] | None = None
    repair_patches_json: list[dict[str, Any]] | None = None
    summary_text: str | None = None
    summary_json: dict[str, Any] | None = None
    events_json: list[dict[str, Any]] = Field(default_factory=list)
    artifacts_json: dict[str, Any] = Field(default_factory=dict)
    runner_job_id: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SavedTest(BaseModel):
    """Reusable browser TestConfig; execute it with tests.run(test.id)."""

    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    prompt: str
    start_url: str
    test_config_json: dict[str, Any]
    source_run_id: str | None = None
    description: str | None = None
    repo_full_name: str | None = None
    ci_enabled: bool = False
    has_credentials: bool = False
    credential_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TrainingDataset(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    source: str
    trace_count: int
    project_id: str | None = None
    created_at: datetime | None = None


class TrainingTask(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    trace_id: str
    status: Literal["draft", "approved", "rejected"]
    revision: int
    spec: dict[str, Any]
    variation: str = ""
    scenario_id: str | None = None
    reviewed_at: datetime | None = None
    review_history: list[dict[str, Any]] = Field(default_factory=list)


class TrainingDatasetDetail(TrainingDataset):
    traces: list[dict[str, Any]] = Field(default_factory=list)
    snapshots: dict[str, Any] = Field(default_factory=dict)
    tasks: list[TrainingTask] = Field(default_factory=list)


# Resolve response types declared later in this module on Python 3.10 too.
TwinProvisionStatus.model_rebuild()
Scenario.model_rebuild()
