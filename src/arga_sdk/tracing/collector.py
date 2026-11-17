"""Episode boundaries, context isolation and bounded background export of projected data."""

from __future__ import annotations

import asyncio
import functools
import inspect
import json
import os
import queue
import secrets
import threading
import time
import uuid
from collections import Counter, deque
from collections.abc import Callable, Sequence
from contextvars import ContextVar
from typing import Any, TypeVar, cast

import httpx

from .models import MAX_EVIDENCE_BYTES, Episode
from .projection import READS, CapturePolicy, Projector

_ACTIVE: ContextVar[object] = ContextVar("arga_evidence_episode", default=None)
Client = TypeVar("Client")


class Exporter:
    def __init__(self, api_key, base_url, capacity, timeout):
        self.queue = queue.Queue(maxsize=capacity)
        self.condition = threading.Condition()
        self.stopping = threading.Event()
        self.stats = Counter()
        self.receipts = deque(maxlen=20)
        self.client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            follow_redirects=False,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        )
        self.worker = threading.Thread(target=self._run, name="arga-evidence-export", daemon=True)
        self.worker.start()

    def submit(self, episode):
        # The queue contains immutable, validated, minimized JSON bytes only.
        try:
            payload = json.dumps(
                Episode.model_validate(episode.payload()).payload(), allow_nan=False
            ).encode()
            if len(payload) > MAX_EVIDENCE_BYTES:
                raise ValueError("Evidence limit")
            with self.condition:
                if self.stopping.is_set():
                    self.stats["dropped"] += 1
                    return False
                self.queue.put_nowait(payload)
                self.stats["queued"] += 1
            return True
        except Exception:
            with self.condition:
                self.stats["dropped"] += 1
            return False

    def _send(self, payload):
        for attempt in range(3):
            try:
                response = self.client.post("/datasets/evidence", content=payload)
                if response.is_success:
                    result = response.json()
                    dataset_id = str(uuid.UUID(result["id"]))
                    with self.condition:
                        self.receipts.append({"id": dataset_id, "training_path": "/training/" + dataset_id})
                    return True
                if response.status_code != 429 and response.status_code < 500:
                    return False
            except Exception:
                # Provider/HTTP exception strings and bodies may contain source data.
                pass
            if attempt < 2:
                time.sleep(0.1 * 2**attempt)
        return False

    def _run(self):
        try:
            while not self.stopping.is_set() or not self.queue.empty():
                try:
                    payload = self.queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    outcome = "uploaded" if self._send(payload) else "failed"
                    with self.condition:
                        self.stats[outcome] += 1
                finally:
                    self.queue.task_done()
                    with self.condition:
                        self.condition.notify_all()
        finally:
            self.client.close()

    def flush(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.queue.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(remaining)
        return True

    def close(self, timeout=5.0):
        with self.condition:
            self.stopping.set()
        drained = self.flush(timeout)
        self.worker.join(timeout=0.2)
        return drained


class EpisodeContext:
    def __init__(self, collector, goal, policies, episode_key=None):
        self.collector = collector
        self.projector = Projector(
            source=collector.source,
            episode_key=episode_key or uuid.uuid4().hex,
            alias_key=collector.alias_key,
            policy=collector.policy,
        )
        self.projector.set_goal(goal, policies)
        self.lock = threading.RLock()
        self.in_flight = 0
        self.writes_in_flight = 0
        self.finished = False

    def __enter__(self):
        self.token = _ACTIVE.set(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        _ACTIVE.reset(self.token)
        with self.lock:
            self.finished = True
            if exc_type:
                self.projector.issue("agent_error")
            if self.in_flight:
                self.projector.issue("source_incomplete")
            self.collector.submit(self.projector.episode)

    def preview(self):
        return self.projector.episode.payload()


class Tracing:
    def __init__(
        self,
        *,
        source: str,
        policy: CapturePolicy | None = None,
        api_key: str | None = None,
        base_url: str = "https://api.argalabs.com",
        alias_key: bytes | None = None,
        upload: bool = True,
        queue_size: int = 32,
        request_timeout: float = 5.0,
    ) -> None:
        if not 1 <= queue_size <= 1000 or not 0 < request_timeout <= 60:
            raise ValueError("Invalid exporter bounds")
        self.source, self.policy = source, policy or CapturePolicy()
        self.alias_key = alias_key if alias_key is not None else secrets.token_bytes(32)
        # Validate configuration before any instrumentation runs.
        Projector(source=source, episode_key="config", alias_key=self.alias_key, policy=self.policy)
        if upload and not (api_key or os.environ.get("ARGA_TRACE_KEY")):
            raise ValueError(
                "Set ARGA_TRACE_KEY or pass an Arga upload key; use upload=False for local preview"
            )
        parsed = httpx.URL(base_url)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.host in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Use HTTPS for evidence uploads")
        self.exporter = (
            Exporter(api_key or os.environ.get("ARGA_TRACE_KEY"), base_url, queue_size, request_timeout)
            if upload
            else None
        )
        self.last_episode: dict[str, Any] | None = None

    def episode(
        self, *, goal: str | None = None, policies: Sequence[str] = (), episode_key: str | None = None
    ) -> EpisodeContext:
        return EpisodeContext(self, goal, policies, episode_key)

    def agent(self, *, goal: Callable[..., str] | None = None, policies: Sequence[str] = ()):
        def decorate(function):
            if inspect.isgeneratorfunction(function) or inspect.isasyncgenfunction(function):
                raise ValueError("Use an explicit episode around generator consumption")

            def selected(args, kwargs):
                try:
                    return goal(*args, **kwargs) if goal else None
                except Exception:
                    return None

            if inspect.iscoroutinefunction(function):

                @functools.wraps(function)
                async def asynchronous(*args, **kwargs):
                    with self.episode(goal=selected(args, kwargs), policies=policies):
                        return await function(*args, **kwargs)

                return asynchronous

            @functools.wraps(function)
            def synchronous(*args, **kwargs):
                with self.episode(goal=selected(args, kwargs), policies=policies):
                    return function(*args, **kwargs)

            return synchronous

        return decorate

    def current(self):
        current = _ACTIVE.get()
        return (
            current
            if isinstance(current, EpisodeContext) and current.collector is self and not current.finished
            else None
        )

    def _start(self, operation):
        current = self.current()
        if current:
            with current.lock:
                write = operation is None or operation[2] not in READS
                if current.in_flight and (write or current.writes_in_flight):
                    # A completion-order list cannot establish pre-mutation state for overlapping calls.
                    current.projector.issue("source_incomplete")
                current.in_flight += 1
                current.writes_in_flight += int(write)
        return current

    def _end(self, current, operation, parameters, result=None, error=None):
        if current:
            with current.lock:
                current.in_flight -= 1
                current.writes_in_flight -= int(operation is None or operation[2] not in READS)
                if current.finished:
                    return
                if operation is None:
                    current.projector.issue("unsupported_operation")
                else:
                    current.projector.record(*operation, parameters, result, error)

    def call(self, function, operation, parameters, args, kwargs):
        current = self._start(operation)
        try:
            result = function(*args, **kwargs)
        except BaseException as exc:
            self._end(current, operation, parameters, error=exc)
            raise
        self._end(current, operation, parameters, result=result)
        return result

    async def call_async(self, function, operation, parameters, args, kwargs):
        current = self._start(operation)
        try:
            result = await function(*args, **kwargs)
        except BaseException as exc:
            self._end(current, operation, parameters, error=exc)
            raise
        self._end(current, operation, parameters, result=result)
        return result

    def wrap_stripe(self, client: Client) -> Client:
        from .adapters import StripeProxy

        return cast(Client, StripeProxy(client, self))

    def wrap_gmail(self, service: Client) -> Client:
        from .adapters import GmailProxy

        return cast(Client, GmailProxy(service, self))

    def submit(self, episode):
        try:
            # Detach from the context before handing it to background code.
            episode = Episode.model_validate(episode.payload())
            self.last_episode = episode.payload()
            return self.exporter.submit(episode) if self.exporter else True
        except Exception:
            if self.exporter:
                with self.exporter.condition:
                    self.exporter.stats["dropped"] += 1
            return False

    def flush(self, timeout: float = 5.0) -> bool:
        return self.exporter.flush(timeout) if self.exporter else True

    async def aflush(self, timeout: float = 5.0) -> bool:
        return await asyncio.to_thread(self.flush, timeout)

    def close(self, timeout: float = 5.0) -> bool:
        return self.exporter.close(timeout) if self.exporter else True

    def diagnostics(self) -> dict[str, int]:
        """Content-free counters. A drained queue is not proof that every upload succeeded."""
        if not self.exporter:
            return {}
        with self.exporter.condition:
            return dict(self.exporter.stats)

    def recent_uploads(self) -> list[dict[str, str]]:
        """Bounded upload receipts; includes only dataset IDs and relative Training paths."""
        if not self.exporter:
            return []
        with self.exporter.condition:
            return list(self.exporter.receipts)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def init(
    *,
    source: str,
    policy: CapturePolicy | None = None,
    api_key: str | None = None,
    base_url: str = "https://api.argalabs.com",
    alias_key: bytes | None = None,
    upload: bool = True,
    queue_size: int = 32,
    request_timeout: float = 5.0,
) -> Tracing:
    """Configure local collection. Wrap provider clients explicitly; never patch global libraries."""
    return Tracing(
        source=source,
        policy=policy,
        api_key=api_key,
        base_url=base_url,
        alias_key=alias_key,
        upload=upload,
        queue_size=queue_size,
        request_timeout=request_timeout,
    )
