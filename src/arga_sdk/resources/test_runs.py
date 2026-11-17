"""Browser Test Runs on the current /test-runs REST API."""

import asyncio
import time
from typing import Any

from typing_extensions import Unpack

from arga_sdk._http import AsyncHTTPClient, SyncHTTPClient
from arga_sdk.exceptions import ArgaError
from arga_sdk.options import (
    TestRunCreate,
    TestRunOptions,
    TestRunOverrides,
    request_body,
)
from arga_sdk.types import TestRun

from ._common import artifact_path, polling_bounds, segment

_TERMINAL = {"completed", "failed", "cancelled"}


class SyncTestRuns:
    def __init__(self, http: SyncHTTPClient):
        self._http = http

    def create(self, prompt: str, **options: Unpack[TestRunOptions]) -> TestRun:
        return TestRun.model_validate(
            self._http.post("/test-runs", json=request_body(TestRunCreate, {"prompt": prompt, **options}))
        )

    def list(self) -> list[TestRun]:
        return [TestRun.model_validate(item) for item in self._http.get("/test-runs")["runs"]]

    def get(self, run_id: str) -> TestRun:
        return TestRun.model_validate(self._http.get(f"/test-runs/{segment(run_id)}"))

    def rerun(self, run_id: str, **overrides: Unpack[TestRunOverrides]) -> TestRun:
        return TestRun.model_validate(
            self._http.post(f"/test-runs/{segment(run_id)}/rerun", json=request_body(TestRunOverrides, overrides))
        )

    def update_config(self, run_id: str, test_config: dict[str, Any]) -> TestRun:
        return TestRun.model_validate(
            self._http.patch(f"/test-runs/{segment(run_id)}/config", json={"test_config": test_config})
        )

    def send_message(self, run_id: str, message: str) -> TestRun:
        return TestRun.model_validate(
            self._http.post(f"/test-runs/{segment(run_id)}/messages", json={"message": message})
        )

    def artifact_url(self, run_id: str, filename: str) -> str:
        """Return a signed storage URL without forwarding the Arga credential to it."""
        return self._http.get_redirect(f"/test-runs/{segment(run_id)}/artifacts/{artifact_path(filename)}")

    def wait(self, run_id: str, *, poll_interval: float = 2.5, timeout: float = 600) -> TestRun:
        polling_bounds(poll_interval, timeout)
        deadline = time.monotonic() + timeout
        while True:
            run = self.get(run_id)
            if run.status in _TERMINAL:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ArgaError(f"Timed out waiting for Test Run {run_id}")
            time.sleep(min(poll_interval, remaining))


class AsyncTestRuns:
    def __init__(self, http: AsyncHTTPClient):
        self._http = http

    async def create(self, prompt: str, **options: Unpack[TestRunOptions]) -> TestRun:
        return TestRun.model_validate(
            await self._http.post("/test-runs", json=request_body(TestRunCreate, {"prompt": prompt, **options}))
        )

    async def list(self) -> list[TestRun]:
        return [TestRun.model_validate(item) for item in (await self._http.get("/test-runs"))["runs"]]

    async def get(self, run_id: str) -> TestRun:
        return TestRun.model_validate(await self._http.get(f"/test-runs/{segment(run_id)}"))

    async def rerun(self, run_id: str, **overrides: Unpack[TestRunOverrides]) -> TestRun:
        return TestRun.model_validate(
            await self._http.post(f"/test-runs/{segment(run_id)}/rerun", json=request_body(TestRunOverrides, overrides))
        )

    async def update_config(self, run_id: str, test_config: dict[str, Any]) -> TestRun:
        return TestRun.model_validate(
            await self._http.patch(f"/test-runs/{segment(run_id)}/config", json={"test_config": test_config})
        )

    async def send_message(self, run_id: str, message: str) -> TestRun:
        return TestRun.model_validate(
            await self._http.post(f"/test-runs/{segment(run_id)}/messages", json={"message": message})
        )

    async def artifact_url(self, run_id: str, filename: str) -> str:
        return await self._http.get_redirect(f"/test-runs/{segment(run_id)}/artifacts/{artifact_path(filename)}")

    async def wait(self, run_id: str, *, poll_interval: float = 2.5, timeout: float = 600) -> TestRun:
        polling_bounds(poll_interval, timeout)
        deadline = time.monotonic() + timeout
        while True:
            run = await self.get(run_id)
            if run.status in _TERMINAL:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ArgaError(f"Timed out waiting for Test Run {run_id}")
            await asyncio.sleep(min(poll_interval, remaining))
