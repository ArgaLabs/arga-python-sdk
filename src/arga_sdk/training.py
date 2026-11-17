"""Training control-plane helpers. Agent instrumentation should use upload-only keys."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, SecretStr

from .resources._common import segment
from .tracing.models import Episode
from .types import (
    ScenarioTwinEnvironment,
    TrainingDataset,
    TrainingDatasetDetail,
    TrainingTask,
)


class EvidenceUploadKey(BaseModel):
    key: SecretStr
    source: str
    expires_at: datetime
    scope: str


class SyncTraining:
    def __init__(self, http):
        self._http = http

    def create_upload_key(self, *, source: str) -> EvidenceUploadKey:
        return EvidenceUploadKey.model_validate(self._http.post("/datasets/evidence-key", json={"source": source}))

    def upload_evidence(self, episode: Episode) -> dict:
        return self._http.post("/datasets/evidence", json=Episode.model_validate(episode.payload()).payload())

    def list(self, *, limit: int = 50, offset: int = 0) -> list[TrainingDataset]:
        return [
            TrainingDataset.model_validate(item)
            for item in self._http.get("/datasets", params={"limit": limit, "offset": offset})
        ]

    def get(self, dataset_id: str) -> TrainingDatasetDetail:
        return TrainingDatasetDetail.model_validate(self._http.get(f"/datasets/{segment(dataset_id)}"))

    def generate_task(self, dataset_id: str, *, trace_id: str, variation: str = "") -> TrainingTask:
        return TrainingTask.model_validate(
            self._http.post(
                f"/datasets/{segment(dataset_id)}/tasks", json={"trace_id": trace_id, "variation": variation}
            )
        )

    def update_task(self, dataset_id: str, task_id: str, *, revision: int, spec: dict[str, Any]) -> TrainingTask:
        return TrainingTask.model_validate(
            self._http.put(
                f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}", json={"revision": revision, "spec": spec}
            )
        )

    def review_task(
        self,
        dataset_id: str,
        task_id: str,
        *,
        revision: int,
        decision: Literal["approved", "rejected"],
        acknowledge_assumptions: bool = False,
        acknowledge_grader: bool = False,
    ) -> TrainingTask:
        return TrainingTask.model_validate(
            self._http.post(
                f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/review",
                json={
                    "revision": revision,
                    "decision": decision,
                    "acknowledge_assumptions": acknowledge_assumptions,
                    "acknowledge_grader": acknowledge_grader,
                },
            )
        )

    def prepare_grader(self, dataset_id: str, task_id: str, *, revision: int) -> TrainingTask:
        return TrainingTask.model_validate(
            self._http.post(
                f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/grader", json={"revision": revision}
            )
        )

    def get_grader(self, dataset_id: str, task_id: str) -> dict[str, Any]:
        return self._http.get(f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/grader")

    def test_grader(
        self, dataset_id: str, task_id: str, *, revision: int, before: dict[str, Any], after: dict[str, Any]
    ) -> dict[str, Any]:
        return self._http.post(
            f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/grader/test",
            json={"revision": revision, "before": before, "after": after},
        )

    def create_environment(self, dataset_id: str, task_id: str) -> ScenarioTwinEnvironment:
        return ScenarioTwinEnvironment.model_validate(
            self._http.post(f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/environment")
        )

    def export_jsonl(self, dataset_id: str) -> str:
        return self._http.get_text(f"/datasets/{segment(dataset_id)}/export")


class AsyncTraining:
    def __init__(self, http):
        self._http = http

    async def create_upload_key(self, *, source: str) -> EvidenceUploadKey:
        return EvidenceUploadKey.model_validate(
            await self._http.post("/datasets/evidence-key", json={"source": source})
        )

    async def upload_evidence(self, episode: Episode) -> dict:
        return await self._http.post("/datasets/evidence", json=Episode.model_validate(episode.payload()).payload())

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[TrainingDataset]:
        return [
            TrainingDataset.model_validate(item)
            for item in await self._http.get("/datasets", params={"limit": limit, "offset": offset})
        ]

    async def get(self, dataset_id: str) -> TrainingDatasetDetail:
        return TrainingDatasetDetail.model_validate(await self._http.get(f"/datasets/{segment(dataset_id)}"))

    async def generate_task(self, dataset_id: str, *, trace_id: str, variation: str = "") -> TrainingTask:
        return TrainingTask.model_validate(
            await self._http.post(
                f"/datasets/{segment(dataset_id)}/tasks", json={"trace_id": trace_id, "variation": variation}
            )
        )

    async def update_task(self, dataset_id: str, task_id: str, *, revision: int, spec: dict[str, Any]) -> TrainingTask:
        return TrainingTask.model_validate(
            await self._http.put(
                f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}", json={"revision": revision, "spec": spec}
            )
        )

    async def review_task(
        self,
        dataset_id: str,
        task_id: str,
        *,
        revision: int,
        decision: Literal["approved", "rejected"],
        acknowledge_assumptions: bool = False,
        acknowledge_grader: bool = False,
    ) -> TrainingTask:
        return TrainingTask.model_validate(
            await self._http.post(
                f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/review",
                json={
                    "revision": revision,
                    "decision": decision,
                    "acknowledge_assumptions": acknowledge_assumptions,
                    "acknowledge_grader": acknowledge_grader,
                },
            )
        )

    async def prepare_grader(self, dataset_id: str, task_id: str, *, revision: int) -> TrainingTask:
        return TrainingTask.model_validate(
            await self._http.post(
                f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/grader", json={"revision": revision}
            )
        )

    async def get_grader(self, dataset_id: str, task_id: str) -> dict[str, Any]:
        return await self._http.get(f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/grader")

    async def test_grader(
        self, dataset_id: str, task_id: str, *, revision: int, before: dict[str, Any], after: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._http.post(
            f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/grader/test",
            json={"revision": revision, "before": before, "after": after},
        )

    async def create_environment(self, dataset_id: str, task_id: str) -> ScenarioTwinEnvironment:
        return ScenarioTwinEnvironment.model_validate(
            await self._http.post(f"/datasets/{segment(dataset_id)}/tasks/{segment(task_id)}/environment")
        )

    async def export_jsonl(self, dataset_id: str) -> str:
        return await self._http.get_text(f"/datasets/{segment(dataset_id)}/export")
