"""Canonical Twin Runs; reset currently retains the backend's existing reset route."""

import asyncio
import time
from typing import Any

from typing_extensions import Unpack

from arga_sdk._http import AsyncHTTPClient, SyncHTTPClient
from arga_sdk.exceptions import ArgaError
from arga_sdk.options import TwinRunCreate, TwinRunExtend, TwinRunOptions, request_body
from arga_sdk.types import TwinProvisionStatus, TwinResetResult, TwinRun

from ._common import polling_bounds, segment

_TERMINAL = {"ready", "failed", "cancelled", "expired", "torn_down", "error", "timed_out"}


class SyncTwinRuns:
    def __init__(self, http: SyncHTTPClient):
        self._http = http

    def create(self, twins: list[str], **options: Unpack[TwinRunOptions]) -> TwinRun:
        return TwinRun.model_validate(
            self._http.post("/twin-runs", json=request_body(TwinRunCreate, {"twins": twins, **options}))
        )

    def get(self, run_id: str) -> TwinProvisionStatus:
        return TwinProvisionStatus.model_validate(self._http.get(f"/twin-runs/{segment(run_id)}"))

    def extend(self, run_id: str, *, ttl_minutes: int = 60) -> dict[str, Any]:
        return self._http.post(
            f"/twin-runs/{segment(run_id)}/extend", json=request_body(TwinRunExtend, {"ttl_minutes": ttl_minutes})
        )

    def teardown(self, run_id: str) -> dict[str, Any]:
        return self._http.post(f"/twin-runs/{segment(run_id)}/teardown")

    def lock(self, run_id: str) -> dict[str, Any]:
        return self._http.post(f"/twin-runs/{segment(run_id)}/lock")

    def reset(self, run_id: str) -> TwinResetResult:
        return TwinResetResult.model_validate(self._http.post(f"/validate/twins/provision/{segment(run_id)}/reset"))

    def microsoft_scenario_snapshot(self, run_id: str) -> dict[str, Any]:
        return self._http.get(f"/twin-runs/{segment(run_id)}/microsoft-scenario-snapshot")

    def wait(self, run_id: str, *, poll_interval: float = 2.5, timeout: float = 600) -> TwinProvisionStatus:
        polling_bounds(poll_interval, timeout)
        deadline = time.monotonic() + timeout
        while True:
            status = self.get(run_id)
            if status.status in _TERMINAL:
                return status
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ArgaError(f"Timed out waiting for Twin Run {run_id}")
            time.sleep(min(poll_interval, remaining))


class AsyncTwinRuns:
    def __init__(self, http: AsyncHTTPClient):
        self._http = http

    async def create(self, twins: list[str], **options: Unpack[TwinRunOptions]) -> TwinRun:
        return TwinRun.model_validate(
            await self._http.post("/twin-runs", json=request_body(TwinRunCreate, {"twins": twins, **options}))
        )

    async def get(self, run_id: str) -> TwinProvisionStatus:
        return TwinProvisionStatus.model_validate(await self._http.get(f"/twin-runs/{segment(run_id)}"))

    async def extend(self, run_id: str, *, ttl_minutes: int = 60) -> dict[str, Any]:
        return await self._http.post(
            f"/twin-runs/{segment(run_id)}/extend", json=request_body(TwinRunExtend, {"ttl_minutes": ttl_minutes})
        )

    async def teardown(self, run_id: str) -> dict[str, Any]:
        return await self._http.post(f"/twin-runs/{segment(run_id)}/teardown")

    async def lock(self, run_id: str) -> dict[str, Any]:
        return await self._http.post(f"/twin-runs/{segment(run_id)}/lock")

    async def reset(self, run_id: str) -> TwinResetResult:
        return TwinResetResult.model_validate(
            await self._http.post(f"/validate/twins/provision/{segment(run_id)}/reset")
        )

    async def microsoft_scenario_snapshot(self, run_id: str) -> dict[str, Any]:
        return await self._http.get(f"/twin-runs/{segment(run_id)}/microsoft-scenario-snapshot")

    async def wait(self, run_id: str, *, poll_interval: float = 2.5, timeout: float = 600) -> TwinProvisionStatus:
        polling_bounds(poll_interval, timeout)
        deadline = time.monotonic() + timeout
        while True:
            status = await self.get(run_id)
            if status.status in _TERMINAL:
                return status
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ArgaError(f"Timed out waiting for Twin Run {run_id}")
            await asyncio.sleep(min(poll_interval, remaining))
