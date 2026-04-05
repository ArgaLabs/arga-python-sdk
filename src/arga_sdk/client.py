from __future__ import annotations

import asyncio
import time
from typing import Any, Iterator, AsyncIterator

from arga_sdk._http import AsyncHTTPClient, SyncHTTPClient
from arga_sdk.exceptions import ArgaError
from arga_sdk.types import (
    Run,
    RunDetail,
    Scenario,
    Twin,
    TwinProvisionStatus,
)

_DEFAULT_BASE_URL = "https://app.argalabs.com"
_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


# ---------------------------------------------------------------------------
# Sync namespace classes
# ---------------------------------------------------------------------------


class _SyncRuns:
    """Synchronous methods for the /validate and /runs endpoints."""

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def create_url_run(
        self,
        url: str,
        *,
        prompt: str | None = None,
        twins: list[str] | None = None,
        credentials: dict[str, Any] | None = None,
        runner_mode: str | None = None,
        session_id: str | None = None,
    ) -> Run:
        body: dict[str, Any] = {"url": url}
        if prompt is not None:
            body["prompt"] = prompt
        if twins is not None:
            body["twins"] = twins
        if credentials is not None:
            body["credentials"] = credentials
        if runner_mode is not None:
            body["runner_mode"] = runner_mode
        if session_id is not None:
            body["session_id"] = session_id
        data = self._http.post("/validate/url-run", json=body)
        return Run.model_validate(data)

    def create_pr_run(
        self,
        repo: str,
        *,
        branch: str | None = None,
        pr_url: str | None = None,
        context_notes: str | None = None,
        scenario_prompt: str | None = None,
        twins: list[str] | None = None,
        frontend_url: str | None = None,
        session_id: str | None = None,
    ) -> Run:
        body: dict[str, Any] = {"repo": repo}
        if branch is not None:
            body["branch"] = branch
        if pr_url is not None:
            body["pr_url"] = pr_url
        if context_notes is not None:
            body["context_notes"] = context_notes
        if scenario_prompt is not None:
            body["scenario_prompt"] = scenario_prompt
        if twins is not None:
            body["twins"] = twins
        if frontend_url is not None:
            body["frontend_url"] = frontend_url
        if session_id is not None:
            body["session_id"] = session_id
        data = self._http.post("/validate/pr-run", json=body)
        return Run.model_validate(data)

    def create_agent_run(
        self,
        *,
        url: str | None = None,
        repo: str | None = None,
        branch: str | None = None,
        credentials: list[dict[str, Any]] | None = None,
        focus: str | None = None,
        action_budget: int = 200,
        runner_mode: str | None = None,
    ) -> Run:
        body: dict[str, Any] = {"action_budget": action_budget}
        if url is not None:
            body["url"] = url
        if repo is not None:
            body["repo"] = repo
        if branch is not None:
            body["branch"] = branch
        if credentials is not None:
            body["credentials"] = credentials
        if focus is not None:
            body["focus"] = focus
        if runner_mode is not None:
            body["runner_mode"] = runner_mode
        data = self._http.post("/validate/agent-run", json=body)
        return Run.model_validate(data)

    def get(self, run_id: str) -> RunDetail:
        data = self._http.get(f"/runs/{run_id}")
        return RunDetail.model_validate(data)

    def stream_results(self, run_id: str) -> Iterator[dict[str, Any]]:
        return self._http.stream_sse(f"/validate/{run_id}/results")

    def cancel(self, run_id: str) -> dict[str, str]:
        data = self._http.post(f"/validate/{run_id}/cancel")
        return data  # type: ignore[return-value]

    def wait(
        self,
        run_id: str,
        *,
        poll_interval: float = 2.5,
        timeout: float = 600,
    ) -> RunDetail:
        """Poll until the run reaches a terminal status."""
        start = time.monotonic()
        while True:
            detail = self.get(run_id)
            if detail.status in _TERMINAL_STATUSES:
                return detail
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise ArgaError(
                    f"Timed out waiting for run {run_id} after {timeout}s "
                    f"(last status: {detail.status})"
                )
            time.sleep(poll_interval)


class _SyncTwins:
    """Synchronous methods for twin endpoints."""

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def list(self) -> list[Twin]:
        data = self._http.get("/validate/twins")
        return [Twin.model_validate(item) for item in data]

    def provision(
        self,
        twins: list[str],
        *,
        ttl_minutes: int = 60,
        scenario_id: str | None = None,
    ) -> dict[str, str]:
        body: dict[str, Any] = {"twins": twins, "ttl_minutes": ttl_minutes}
        if scenario_id is not None:
            body["scenario_id"] = scenario_id
        return self._http.post("/validate/twins/provision", json=body)  # type: ignore[return-value]

    def get_status(self, run_id: str) -> TwinProvisionStatus:
        data = self._http.get(f"/validate/twins/provision/{run_id}/status")
        return TwinProvisionStatus.model_validate(data)

    def extend(self, run_id: str, *, ttl_minutes: int = 60) -> dict[str, Any]:
        body: dict[str, Any] = {"ttl_minutes": ttl_minutes}
        return self._http.post(  # type: ignore[return-value]
            f"/validate/twins/provision/{run_id}/extend", json=body
        )


class _SyncScenarios:
    """Synchronous methods for scenario endpoints."""

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def create(
        self,
        name: str,
        *,
        prompt: str | None = None,
        seed_config: dict[str, Any] | None = None,
        twins: list[str] | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Scenario:
        body: dict[str, Any] = {"name": name}
        if prompt is not None:
            body["prompt"] = prompt
        if seed_config is not None:
            body["seed_config"] = seed_config
        if twins is not None:
            body["twins"] = twins
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        data = self._http.post("/scenarios", json=body)
        return Scenario.model_validate(data)

    def list(
        self,
        *,
        twin: str | None = None,
        tag: str | None = None,
    ) -> list[Scenario]:
        params: dict[str, str] = {}
        if twin is not None:
            params["twin"] = twin
        if tag is not None:
            params["tag"] = tag
        data = self._http.get("/scenarios", params=params or None)
        return [Scenario.model_validate(item) for item in data]

    def get(self, scenario_id: str) -> Scenario:
        data = self._http.get(f"/scenarios/{scenario_id}")
        return Scenario.model_validate(data)


# ---------------------------------------------------------------------------
# Async namespace classes
# ---------------------------------------------------------------------------


class _AsyncRuns:
    """Asynchronous methods for the /validate and /runs endpoints."""

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create_url_run(
        self,
        url: str,
        *,
        prompt: str | None = None,
        twins: list[str] | None = None,
        credentials: dict[str, Any] | None = None,
        runner_mode: str | None = None,
        session_id: str | None = None,
    ) -> Run:
        body: dict[str, Any] = {"url": url}
        if prompt is not None:
            body["prompt"] = prompt
        if twins is not None:
            body["twins"] = twins
        if credentials is not None:
            body["credentials"] = credentials
        if runner_mode is not None:
            body["runner_mode"] = runner_mode
        if session_id is not None:
            body["session_id"] = session_id
        data = await self._http.post("/validate/url-run", json=body)
        return Run.model_validate(data)

    async def create_pr_run(
        self,
        repo: str,
        *,
        branch: str | None = None,
        pr_url: str | None = None,
        context_notes: str | None = None,
        scenario_prompt: str | None = None,
        twins: list[str] | None = None,
        frontend_url: str | None = None,
        session_id: str | None = None,
    ) -> Run:
        body: dict[str, Any] = {"repo": repo}
        if branch is not None:
            body["branch"] = branch
        if pr_url is not None:
            body["pr_url"] = pr_url
        if context_notes is not None:
            body["context_notes"] = context_notes
        if scenario_prompt is not None:
            body["scenario_prompt"] = scenario_prompt
        if twins is not None:
            body["twins"] = twins
        if frontend_url is not None:
            body["frontend_url"] = frontend_url
        if session_id is not None:
            body["session_id"] = session_id
        data = await self._http.post("/validate/pr-run", json=body)
        return Run.model_validate(data)

    async def create_agent_run(
        self,
        *,
        url: str | None = None,
        repo: str | None = None,
        branch: str | None = None,
        credentials: list[dict[str, Any]] | None = None,
        focus: str | None = None,
        action_budget: int = 200,
        runner_mode: str | None = None,
    ) -> Run:
        body: dict[str, Any] = {"action_budget": action_budget}
        if url is not None:
            body["url"] = url
        if repo is not None:
            body["repo"] = repo
        if branch is not None:
            body["branch"] = branch
        if credentials is not None:
            body["credentials"] = credentials
        if focus is not None:
            body["focus"] = focus
        if runner_mode is not None:
            body["runner_mode"] = runner_mode
        data = await self._http.post("/validate/agent-run", json=body)
        return Run.model_validate(data)

    async def get(self, run_id: str) -> RunDetail:
        data = await self._http.get(f"/runs/{run_id}")
        return RunDetail.model_validate(data)

    async def stream_results(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        async for event in self._http.stream_sse(f"/validate/{run_id}/results"):
            yield event

    async def cancel(self, run_id: str) -> dict[str, str]:
        data = await self._http.post(f"/validate/{run_id}/cancel")
        return data  # type: ignore[return-value]

    async def wait(
        self,
        run_id: str,
        *,
        poll_interval: float = 2.5,
        timeout: float = 600,
    ) -> RunDetail:
        """Poll until the run reaches a terminal status."""
        start = time.monotonic()
        while True:
            detail = await self.get(run_id)
            if detail.status in _TERMINAL_STATUSES:
                return detail
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise ArgaError(
                    f"Timed out waiting for run {run_id} after {timeout}s "
                    f"(last status: {detail.status})"
                )
            await asyncio.sleep(poll_interval)


class _AsyncTwins:
    """Asynchronous methods for twin endpoints."""

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def list(self) -> list[Twin]:
        data = await self._http.get("/validate/twins")
        return [Twin.model_validate(item) for item in data]

    async def provision(
        self,
        twins: list[str],
        *,
        ttl_minutes: int = 60,
        scenario_id: str | None = None,
    ) -> dict[str, str]:
        body: dict[str, Any] = {"twins": twins, "ttl_minutes": ttl_minutes}
        if scenario_id is not None:
            body["scenario_id"] = scenario_id
        return await self._http.post("/validate/twins/provision", json=body)  # type: ignore[return-value]

    async def get_status(self, run_id: str) -> TwinProvisionStatus:
        data = await self._http.get(f"/validate/twins/provision/{run_id}/status")
        return TwinProvisionStatus.model_validate(data)

    async def extend(self, run_id: str, *, ttl_minutes: int = 60) -> dict[str, Any]:
        body: dict[str, Any] = {"ttl_minutes": ttl_minutes}
        return await self._http.post(  # type: ignore[return-value]
            f"/validate/twins/provision/{run_id}/extend", json=body
        )


class _AsyncScenarios:
    """Asynchronous methods for scenario endpoints."""

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def create(
        self,
        name: str,
        *,
        prompt: str | None = None,
        seed_config: dict[str, Any] | None = None,
        twins: list[str] | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Scenario:
        body: dict[str, Any] = {"name": name}
        if prompt is not None:
            body["prompt"] = prompt
        if seed_config is not None:
            body["seed_config"] = seed_config
        if twins is not None:
            body["twins"] = twins
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        data = await self._http.post("/scenarios", json=body)
        return Scenario.model_validate(data)

    async def list(
        self,
        *,
        twin: str | None = None,
        tag: str | None = None,
    ) -> list[Scenario]:
        params: dict[str, str] = {}
        if twin is not None:
            params["twin"] = twin
        if tag is not None:
            params["tag"] = tag
        data = await self._http.get("/scenarios", params=params or None)
        return [Scenario.model_validate(item) for item in data]

    async def get(self, scenario_id: str) -> Scenario:
        data = await self._http.get(f"/scenarios/{scenario_id}")
        return Scenario.model_validate(data)


# ---------------------------------------------------------------------------
# Top-level client classes
# ---------------------------------------------------------------------------


class Arga:
    """Synchronous Arga API client.

    Usage::

        client = Arga(api_key="arga_...")
        run = client.runs.create_url_run(url="https://staging.myapp.com")
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        self._http = SyncHTTPClient(base_url=base_url, api_key=api_key, timeout=timeout)
        self.runs = _SyncRuns(self._http)
        self.twins = _SyncTwins(self._http)
        self.scenarios = _SyncScenarios(self._http)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> Arga:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncArga:
    """Asynchronous Arga API client.

    Usage::

        client = AsyncArga(api_key="arga_...")
        run = await client.runs.create_url_run(url="https://staging.myapp.com")
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        self._http = AsyncHTTPClient(base_url=base_url, api_key=api_key, timeout=timeout)
        self.runs = _AsyncRuns(self._http)
        self.twins = _AsyncTwins(self._http)
        self.scenarios = _AsyncScenarios(self._http)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.close()

    async def __aenter__(self) -> AsyncArga:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
