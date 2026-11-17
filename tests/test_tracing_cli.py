import json
import sys

import pytest

from arga_sdk.tracing import __main__ as cli


def configure(monkeypatch, tmp_path, config=None, extra=()):
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({} if config is None else config))
    monkeypatch.setenv("BRAINTRUST_API_KEY", "local-test-key")
    monkeypatch.setenv("ARGA_TRACE_KEY", "local-test-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "arga-sync",
            "sync",
            "--source",
            "support",
            "--project",
            "00000000-0000-0000-0000-000000000001",
            "--state",
            str(tmp_path / "state"),
            "--since",
            "2026-11-17T00:00:00Z",
            "--policy",
            str(policy),
            *extra,
        ],
    )


@pytest.mark.parametrize(
    "config,extra", [([], ()), ("string", ()), ({}, ("--interval", "nan")), ({}, ("--interval", "inf"))]
)
def test_invalid_config_returns_two_without_traceback(monkeypatch, tmp_path, capsys, config, extra):
    configure(monkeypatch, tmp_path, config, extra)
    assert cli.main() == 2
    assert "Invalid sync configuration" in capsys.readouterr().err


def test_watch_retries_checkpoint_io_error_as_runtime_failure(monkeypatch, tmp_path, capsys):
    configure(monkeypatch, tmp_path, extra=("--watch",))
    calls = []

    class Sync:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def sync_once(self):
            calls.append(True)
            if len(calls) == 1:
                raise OSError("PRIVATE_CANARY")
            raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "BraintrustSync", Sync)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    assert cli.main() == 0 and len(calls) == 2
    error = capsys.readouterr().err
    assert (
        "Sync failed" in error and "Invalid sync configuration" not in error and "PRIVATE_CANARY" not in error
    )
