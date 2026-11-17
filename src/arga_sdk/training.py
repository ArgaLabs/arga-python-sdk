"""Training control-plane helpers. Agent instrumentation should use upload-only keys."""

from datetime import datetime

from pydantic import BaseModel, SecretStr

from .tracing.models import Episode


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


class AsyncTraining:
    def __init__(self, http):
        self._http = http

    async def create_upload_key(self, *, source: str) -> EvidenceUploadKey:
        return EvidenceUploadKey.model_validate(
            await self._http.post("/datasets/evidence-key", json={"source": source})
        )

    async def upload_evidence(self, episode: Episode) -> dict:
        return await self._http.post("/datasets/evidence", json=Episode.model_validate(episode.payload()).payload())
