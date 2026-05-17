from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

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
    "linkedin",
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


class TwinInstance(BaseModel):
    """A provisioned twin instance."""

    model_config = ConfigDict(extra="allow")

    name: str
    label: str | None = None
    base_url: str | None = None
    admin_url: str | None = None
    env_vars: dict[str, str] | None = None
    show_in_ui: bool | None = None


class TwinProvisionStatus(BaseModel):
    """Status of a twin provisioning request."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    status: str
    twins: dict[str, TwinInstance] | None = None
    dashboard_url: str | None = None
    expires_at: datetime | None = None
    proxy_token: str | None = None
    error: str | None = None


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
