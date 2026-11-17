"""Saved Test definitions and their executions."""

from typing import Any

from typing_extensions import Unpack

from arga_sdk._http import AsyncHTTPClient, SyncHTTPClient
from arga_sdk.options import (
    SavedTestCreate,
    SavedTestOptions,
    SavedTestRunOptions,
    SavedTestUpdate,
    request_body,
)
from arga_sdk.types import SavedTest, TestRun

from ._common import segment


class SyncTests:
    def __init__(self, http: SyncHTTPClient):
        self._http = http

    def create(self, name: str, **options: Unpack[SavedTestOptions]) -> SavedTest:
        return SavedTest.model_validate(
            self._http.post("/tests", json=request_body(SavedTestCreate, {"name": name, **options}))
        )

    def list(self, *, repo_full_name: str | None = None) -> list[SavedTest]:
        params = {"repo_full_name": repo_full_name} if repo_full_name is not None else None
        return [SavedTest.model_validate(item) for item in self._http.get("/tests", params=params)["tests"]]

    def get(self, test_id: str) -> SavedTest:
        return SavedTest.model_validate(self._http.get(f"/tests/{segment(test_id)}"))

    def update(self, test_id: str, **changes: Unpack[SavedTestUpdate]) -> SavedTest:
        return SavedTest.model_validate(
            self._http.patch(f"/tests/{segment(test_id)}", json=request_body(SavedTestUpdate, changes))
        )

    def delete(self, test_id: str) -> dict[str, Any]:
        return self._http.delete(f"/tests/{segment(test_id)}")

    def run(self, test_id: str, **overrides: Unpack[SavedTestRunOptions]) -> TestRun:
        return TestRun.model_validate(
            self._http.post(f"/tests/{segment(test_id)}/run", json=request_body(SavedTestRunOptions, overrides))
        )


class AsyncTests:
    def __init__(self, http: AsyncHTTPClient):
        self._http = http

    async def create(self, name: str, **options: Unpack[SavedTestOptions]) -> SavedTest:
        return SavedTest.model_validate(
            await self._http.post("/tests", json=request_body(SavedTestCreate, {"name": name, **options}))
        )

    async def list(self, *, repo_full_name: str | None = None) -> list[SavedTest]:
        params = {"repo_full_name": repo_full_name} if repo_full_name is not None else None
        return [SavedTest.model_validate(item) for item in (await self._http.get("/tests", params=params))["tests"]]

    async def get(self, test_id: str) -> SavedTest:
        return SavedTest.model_validate(await self._http.get(f"/tests/{segment(test_id)}"))

    async def update(self, test_id: str, **changes: Unpack[SavedTestUpdate]) -> SavedTest:
        return SavedTest.model_validate(
            await self._http.patch(f"/tests/{segment(test_id)}", json=request_body(SavedTestUpdate, changes))
        )

    async def delete(self, test_id: str) -> dict[str, Any]:
        return await self._http.delete(f"/tests/{segment(test_id)}")

    async def run(self, test_id: str, **overrides: Unpack[SavedTestRunOptions]) -> TestRun:
        return TestRun.model_validate(
            await self._http.post(f"/tests/{segment(test_id)}/run", json=request_body(SavedTestRunOptions, overrides))
        )
