"""Additional current Scenario operations shared with the legacy-compatible client."""

from typing import Any

from typing_extensions import Unpack

from arga_sdk._http import AsyncHTTPClient, SyncHTTPClient
from arga_sdk.options import ScenarioUpdateOptions, request_body
from arga_sdk.types import Scenario

from ._common import segment


class SyncScenarioOperations:
    _http: SyncHTTPClient

    def update(self, scenario_id: str, **changes: Unpack[ScenarioUpdateOptions]) -> Scenario:
        return Scenario.model_validate(
            self._http.put(f"/scenarios/{segment(scenario_id)}", json=request_body(ScenarioUpdateOptions, changes))
        )

    def delete(self, scenario_id: str) -> dict[str, Any]:
        return self._http.delete(f"/scenarios/{segment(scenario_id)}")

    def copy(self, scenario_id: str, *, name: str | None = None) -> Scenario:
        body = {"name": name} if name is not None else {}
        return Scenario.model_validate(self._http.post(f"/scenarios/{segment(scenario_id)}/copy", json=body))

    def list_presets(self, *, twin: str | None = None, tag: str | None = None) -> list[Scenario]:
        params = {key: value for key, value in {"twin": twin, "tag": tag}.items() if value is not None}
        return [Scenario.model_validate(item) for item in self._http.get("/scenarios/presets", params=params or None)]

    def get_preset(self, scenario_id: str) -> Scenario:
        return Scenario.model_validate(self._http.get(f"/scenarios/presets/{segment(scenario_id)}"))

    def list_long_runs(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self._http.get("/scenarios/long-runs", params={"limit": limit, "offset": offset})


class AsyncScenarioOperations:
    _http: AsyncHTTPClient

    async def update(self, scenario_id: str, **changes: Unpack[ScenarioUpdateOptions]) -> Scenario:
        return Scenario.model_validate(
            await self._http.put(
                f"/scenarios/{segment(scenario_id)}", json=request_body(ScenarioUpdateOptions, changes)
            )
        )

    async def delete(self, scenario_id: str) -> dict[str, Any]:
        return await self._http.delete(f"/scenarios/{segment(scenario_id)}")

    async def copy(self, scenario_id: str, *, name: str | None = None) -> Scenario:
        body = {"name": name} if name is not None else {}
        return Scenario.model_validate(await self._http.post(f"/scenarios/{segment(scenario_id)}/copy", json=body))

    async def list_presets(self, *, twin: str | None = None, tag: str | None = None) -> list[Scenario]:
        params = {key: value for key, value in {"twin": twin, "tag": tag}.items() if value is not None}
        return [
            Scenario.model_validate(item) for item in await self._http.get("/scenarios/presets", params=params or None)
        ]

    async def get_preset(self, scenario_id: str) -> Scenario:
        return Scenario.model_validate(await self._http.get(f"/scenarios/presets/{segment(scenario_id)}"))

    async def list_long_runs(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return await self._http.get("/scenarios/long-runs", params={"limit": limit, "offset": offset})
