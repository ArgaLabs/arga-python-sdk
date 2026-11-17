"""Run with python -m arga_sdk.tracing sync --help. All filtering runs on this host."""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime

from .braintrust import BraintrustSync, SyncError
from .projection import CapturePolicy


def main():
    parser = argparse.ArgumentParser(description="Customer-side Braintrust → Arga Training sync")
    parser.add_argument("command", choices=["sync"])
    parser.add_argument("--source", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--state",
        required=True,
        help="Private local checkpoint; includes the alias key, never provider credentials",
    )
    parser.add_argument("--since", required=True, help="Initial ISO timestamp with timezone")
    parser.add_argument(
        "--policy",
        required=True,
        help="Local JSON policy: text_fields, revision, policies, goal_pointer, operations",
    )
    parser.add_argument("--region", choices=["us", "eu"], default="us")
    parser.add_argument("--arga-url", default="https://api.argalabs.com")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=30)
    args = parser.parse_args()
    try:
        if not math.isfinite(args.interval) or args.interval < 1:
            raise ValueError()
        braintrust_key, arga_key = os.environ["BRAINTRUST_API_KEY"], os.environ["ARGA_TRACE_KEY"]
        with open(args.policy) as stream:
            config = json.load(stream)
        if not isinstance(config, dict) or set(config) - {
            "text_fields",
            "revision",
            "policies",
            "goal_pointer",
            "operations",
        }:
            raise ValueError()
        policy = CapturePolicy(
            text_fields=frozenset(config.get("text_fields", [])), revision=config.get("revision", "1")
        )
        sync = BraintrustSync(
            source=args.source,
            project_id=args.project,
            state_path=args.state,
            since=datetime.fromisoformat(args.since.replace("Z", "+00:00")),
            policy=policy,
            region=args.region,
            braintrust_key=braintrust_key,
            arga_key=arga_key,
            base_url=args.arga_url,
            goal_pointer=config.get("goal_pointer", "/input"),
            policies=config.get("policies", []),
            operations=config.get("operations", {}),
        )
    except (ValueError, KeyError, OSError, TypeError):
        print(
            "Invalid sync configuration. Check environment credentials, policy and timezone-aware start.",
            file=sys.stderr,
        )
        return 2
    try:
        with sync:
            while True:
                try:
                    result = sync.sync_once()
                    print(json.dumps(result), flush=True)
                except (SyncError, OSError):
                    # Never echo exception bodies, SQL, span contents or credentials.
                    print(
                        "Sync failed; checkpoint retained. Check credentials, evidence coverage and local limits.",
                        file=sys.stderr,
                        flush=True,
                    )
                    if not args.watch:
                        return 1
                    result = {"caught_up": True}
                if not args.watch:
                    return 0
                if result["caught_up"]:
                    time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
