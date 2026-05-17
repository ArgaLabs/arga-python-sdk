from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

KnownTwinName: TypeAlias = Literal[
    "box",
    "discord",
    "dropbox",
    "github",
    "gitlab",
    "gmail",
    "google_calendar",
    "google_drive",
    "hubspot",
    "jira",
    "linear",
    "notion",
    "postgres",
    "salesforce",
    "slack",
    "stripe",
    "unified",
    "unstructured",
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
    failure_detail: str | None = None
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
