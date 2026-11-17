"""Customer-run Braintrust sync. Credentials and raw spans never go to Arga."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import secrets
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from .adapters import operation_for
from .models import MAX_EVIDENCE_BYTES
from .projection import READS, CapturePolicy, Projector, value

UTC = timezone.utc


class SyncError(RuntimeError):
    """Content-free diagnostics suitable for a customer's scheduler logs."""


def pointer(document, path):
    if path == "":
        return document
    if not path.startswith("/"):
        raise ValueError("Use a JSON pointer")
    for part in path[1:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        document = document[int(key)] if isinstance(document, list) else document[key]
    return document


def project_trace(
    rows, *, source, project_id, alias_key, policy, goal_pointer="/input", policies=(), operations=None
):
    """Mappings use canonical operation names; no payload inferred from LLM tool suggestions."""
    if not rows or len(rows) > 1000:
        raise SyncError("Select a complete trace with at most 1,000 spans")
    spans = {}
    trace_ids = set()
    for row in rows:
        span_id, trace_id = (
            row.get("span_id") or row.get("id"),
            row.get("root_span_id") or row.get("trace_id"),
        )
        if not isinstance(span_id, str) or not isinstance(trace_id, str):
            raise SyncError("Invalid Braintrust trace identifiers")
        if span_id in spans and spans[span_id] != row:
            raise SyncError("Conflicting Braintrust span revisions")
        spans[span_id] = row
        trace_ids.add(trace_id)
    roots = [span for span in spans.values() if not span.get("span_parents")]
    if len(trace_ids) != 1 or len(roots) != 1:
        raise SyncError("Select one complete trace tree")
    pending = {}
    for span_id, row in spans.items():
        parents = row.get("span_parents") or []
        if not isinstance(parents, list) or any(
            not isinstance(parent, str) or parent not in spans for parent in parents
        ):
            raise SyncError("Braintrust trace has missing parents")
        pending[span_id] = set(parents)
    remaining = dict(pending)
    while remaining:
        ready = {span_id for span_id, parents in remaining.items() if not parents}
        if not ready:
            raise SyncError("Braintrust trace has cyclic parents")
        remaining = {
            span_id: parents - ready for span_id, parents in remaining.items() if span_id not in ready
        }
    projector = Projector(
        source=source,
        episode_key=project_id + ":" + next(iter(trace_ids)),
        alias_key=alias_key,
        policy=policy,
        origin="braintrust",
    )
    try:
        goal = pointer(roots[0], goal_pointer)
    except (KeyError, IndexError, TypeError, ValueError):
        goal = None
    projector.set_goal(goal, policies)
    root_end = value(roots[0].get("metrics"), "end")
    if type(root_end) not in (float, int) or not math.isfinite(root_end):
        projector.issue("source_incomplete")
    mapped = []
    for span in spans.values():
        if span is roots[0]:
            continue
        attributes = span.get("span_attributes") or {}
        if value(attributes, "type") in {"llm", "score", "eval"}:
            continue
        name = value(attributes, "name", "")
        operation = operation_for((operations or {}).get(name, name)) if isinstance(name, str) else None
        if operation is None:
            # Framework and LLM spans are intentionally ignored. Unknown *executed tool*
            # spans are visible coverage gaps, never arbitrary function-input exports.
            if value(attributes, "type") == "tool":
                projector.issue("unsupported_operation")
            continue
        start, end = value(span.get("metrics"), "start"), value(span.get("metrics"), "end")
        if (
            type(start) not in (int, float)
            or type(end) not in (int, float)
            or not math.isfinite(start)
            or not math.isfinite(end)
        ):
            projector.issue("source_incomplete")
            start, end = 0, 0
        mapped.append((start, end, span))
    mapped.sort(key=lambda item: (item[0], str(item[2].get("span_id", ""))))
    active = []
    for start, end, span in mapped:
        name = span["span_attributes"]["name"]
        operation = operation_for((operations or {}).get(name, name))
        write = operation[2] not in READS
        active = [(finish, mutation) for finish, mutation in active if finish > start]
        if end < start or any(write or mutation for _, mutation in active):
            projector.issue("source_incomplete")
        active.append((end, write))
        error = span.get("error")
        # Never export arbitrary error strings/messages. Only structured normalized fields.
        if error and not isinstance(error, dict):
            error = {"code": "other"}
        projector.record(*operation, span.get("input", {}), span.get("output"), error)
    return projector.episode


def _literal(text):
    return "'" + text.replace("'", "''") + "'"


def _query(client, query, *, limit):
    rows, cursor, seen = [], None, set()
    total_bytes = 0
    try:
        for _ in range(100):
            sql = query + (" OFFSET " + _literal(cursor) if cursor else "")
            with client.stream("POST", "/btql", json={"query": sql, "fmt": "json"}) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    total_bytes += len(chunk)
                    if total_bytes > 2_000_000:
                        raise SyncError("Braintrust response exceeds the local limit; reduce the window")
                data = json.loads(body).get("data")
                if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
                    raise SyncError("Invalid Braintrust response")
                rows.extend(data)
                if len(rows) > limit:
                    raise SyncError("Braintrust selection exceeds the local limit; reduce the window")
                cursor = response.headers.get("x-bt-cursor") or response.headers.get("x-amz-meta-bt_cursor")
            if not cursor:
                return rows
            if cursor in seen:
                raise SyncError("Braintrust repeated a pagination cursor")
            seen.add(cursor)
        raise SyncError("Braintrust pagination did not finish")
    except SyncError:
        raise
    except Exception:
        raise SyncError("Braintrust read failed; verify project, region and read credentials") from None


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".arga-sync-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _checkpoint_lock(path):
    # The CLI is intended for a customer-owned Linux/macOS process or container.
    try:
        import fcntl
    except ImportError:
        raise SyncError(
            "Checkpoint sync requires a POSIX host; project_trace is platform independent"
        ) from None
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SyncError("This checkpoint is already in use") from None
        yield
    finally:
        os.close(descriptor)


class BraintrustSync:
    def __init__(
        self,
        *,
        source,
        project_id,
        braintrust_key,
        arga_key,
        state_path,
        since,
        policy=None,
        region="us",
        base_url="https://api.argalabs.com",
        goal_pointer="/input",
        policies=(),
        operations=None,
        window=timedelta(minutes=5),
        lookback=timedelta(minutes=2),
    ):
        self.project_id = str(uuid.UUID(project_id))
        if (
            since.tzinfo is None
            or not timedelta(0) < window <= timedelta(hours=1)
            or not timedelta(0) <= lookback < window
        ):
            raise ValueError("Use a timezone-aware start and a bounded window larger than lookback")
        if region not in {"us", "eu"}:
            raise ValueError("Invalid Braintrust region")
        if httpx.URL(base_url).scheme != "https":
            raise ValueError("Use HTTPS for Arga sync")
        if operations and any(operation_for(operation) is None for operation in operations.values()):
            raise ValueError("Mappings must target supported canonical operations")
        self.source, self.policy, self.path = source, policy or CapturePolicy(), Path(state_path)
        Projector(source=source, episode_key="config", alias_key=b"0" * 32, policy=self.policy)
        self.since, self.window, self.lookback = since.astimezone(UTC), window, lookback
        self.goal_pointer, self.policies, self.operations = goal_pointer, policies, operations or {}
        self.braintrust = httpx.Client(
            base_url="https://api-eu.braintrust.dev" if region == "eu" else "https://api.braintrust.dev",
            headers={"Authorization": "Bearer " + braintrust_key},
            timeout=35,
            follow_redirects=False,
        )
        self.arga = httpx.Client(
            base_url=base_url,
            headers={"Authorization": "Bearer " + arga_key},
            timeout=15,
            follow_redirects=False,
        )
        # Cache identity only; the server still authenticates every request.
        owner = hashlib.sha256(arga_key.encode()).hexdigest()
        if arga_key.startswith("arga_trace_"):
            try:
                segment = arga_key[len("arga_trace_") :].split(".")[1]
                owner = str(
                    uuid.UUID(
                        json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))["sub"]
                    )
                )
            except Exception:
                raise ValueError("Invalid scoped Arga key") from None
        config = {
            "source": source,
            "project_id": self.project_id,
            "policy": self.policy.fingerprint,
            "goal_pointer": goal_pointer,
            "policies": policies,
            "operations": self.operations,
            "region": region,
            "since": self.since.isoformat(),
            "destination": base_url,
            "owner": owner,
        }
        self.identity = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()

    def sync_once(self, *, until=None):
        """Process one time window; retain malformed/unfinished roots locally for retry.

        Advance only after every attempted upload is acknowledged.

        Re-read overlap to detect late/revised spans; the local digest cache suppresses
        unchanged uploads. Children are fetched without a time-window filter.
        """
        until = until or datetime.now(UTC) - timedelta(seconds=30)
        if until.tzinfo is None:
            raise ValueError("Use a timezone-aware end")
        with _checkpoint_lock(self.path):
            if self.path.exists():
                if self.path.stat().st_size > 2_000_000:
                    raise SyncError("Checkpoint exceeds its local limit")
                try:
                    state = json.loads(self.path.read_text())
                    if state["identity"] != self.identity:
                        raise SyncError("Sync configuration changed; use a new checkpoint")
                    key = bytes.fromhex(state["alias_key"])
                    watermark = datetime.fromisoformat(state["watermark"])
                    if len(key) < 32 or watermark.tzinfo is None:
                        raise ValueError()
                except SyncError:
                    raise
                except Exception:
                    raise SyncError("Invalid local checkpoint") from None
            else:
                state = {
                    "identity": self.identity,
                    "alias_key": secrets.token_bytes(32).hex(),
                    "watermark": self.since.isoformat(),
                    "acknowledged": {},
                    "pending": {},
                }
                # Persist aliases before the first request, including on upload failure.
                _save(self.path, state)
                key, watermark = bytes.fromhex(state["alias_key"]), self.since
            start = max(self.since, watermark - self.lookback)
            end = min(until.astimezone(UTC), watermark + self.window)
            if end <= start:
                return {
                    "uploaded": 0,
                    "unchanged": 0,
                    "coverage_gaps": 0,
                    "pending": len(state.get("pending", {})),
                    "caught_up": True,
                }
            roots = _query(
                self.braintrust,
                f"SELECT root_span_id, created FROM project_logs({_literal(self.project_id)}) WHERE is_root = true "
                f"AND created >= {_literal(start.isoformat())} AND created < {_literal(end.isoformat())} ORDER BY created ASC",
                limit=1000,
            )
            pending = state.setdefault("pending", {})
            selected = {root.get("root_span_id"): root for root in roots}
            for trace_id, created in pending.items():
                selected.setdefault(trace_id, {"root_span_id": trace_id, "created": created})
            uploaded = unchanged = gaps = 0
            for root in selected.values():
                trace_id, created = root.get("root_span_id"), root.get("created")
                if not isinstance(trace_id, str) or not isinstance(created, str):
                    raise SyncError("Invalid Braintrust root record")
                try:
                    created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if created_at.tzinfo is None:
                        raise ValueError()
                    created = created_at.astimezone(UTC).isoformat()
                except ValueError:
                    raise SyncError("Invalid Braintrust root timestamp") from None
                rows = _query(
                    self.braintrust,
                    f"SELECT span_id, root_span_id, span_parents, span_attributes, input, output, error, metrics "
                    f"FROM project_logs({_literal(self.project_id)}) WHERE root_span_id = {_literal(trace_id)}",
                    limit=1000,
                )
                root_spans = [row for row in rows if not row.get("span_parents")]
                root_end = value(root_spans[0].get("metrics"), "end") if len(root_spans) == 1 else None
                if len(root_spans) == 1 and (
                    type(root_end) not in (float, int) or not math.isfinite(root_end)
                ):
                    # Keep long-running roots independently of the lookback window.
                    # Do not upload their changing partial payloads or stall newer runs.
                    pending[trace_id] = created
                    if len(pending) > 1000:
                        raise SyncError("Too many unfinished roots; resolve or backfill this source")
                    continue
                try:
                    episode = project_trace(
                        rows,
                        source=self.source,
                        project_id=self.project_id,
                        alias_key=key,
                        policy=self.policy,
                        goal_pointer=self.goal_pointer,
                        policies=self.policies,
                        operations=self.operations,
                    )
                    payload = episode.payload()
                    encoded = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
                    if len(encoded) > MAX_EVIDENCE_BYTES:
                        raise ValueError("Projected episode exceeds the upload limit")
                except (SyncError, ValueError, TypeError, KeyError):
                    # Only root references stay on the customer's host, never raw spans.
                    pending[trace_id] = created
                    gaps += 1
                    if len(pending) > 1000:
                        raise SyncError(
                            "Too many unresolved roots; resolve or backfill this source"
                        ) from None
                    continue
                digest = hashlib.sha256(encoded).hexdigest()
                previous = state["acknowledged"].get(episode.episode_id)
                if previous and previous["digest"] == digest:
                    pending.pop(trace_id, None)
                    unchanged += 1
                    continue
                try:
                    response = self.arga.post(
                        "/datasets/evidence", content=encoded, headers={"Content-Type": "application/json"}
                    )
                    response.raise_for_status()
                    uuid.UUID(response.json()["id"])
                except Exception:
                    raise SyncError("Arga upload was not acknowledged; checkpoint was not advanced") from None
                state["acknowledged"][episode.episode_id] = {"digest": digest, "created": created}
                pending.pop(trace_id, None)
                _save(self.path, state)
                uploaded += 1
            state["watermark"] = max(watermark, end).isoformat()
            cutoff = max(self.since, end - self.lookback).isoformat()
            # Keep only entries in the next overlap window, bounding local state.
            state["acknowledged"] = {
                key: item for key, item in state["acknowledged"].items() if item["created"] >= cutoff
            }
            _save(self.path, state)
            return {
                "uploaded": uploaded,
                "unchanged": unchanged,
                "pending": len(pending),
                "coverage_gaps": gaps,
                "caught_up": end >= until.astimezone(UTC),
            }

    def close(self):
        self.braintrust.close()
        self.arga.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
