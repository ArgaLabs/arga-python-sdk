"""Tiny shared helpers for realistic SDK examples."""

from __future__ import annotations

import json
import os
from typing import Any, NoReturn


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Set {name} before running this example. "
            "See examples/README.md for setup details."
        )
    return value


def print_json(title: str, value: Any) -> None:
    print(f"\n{title}")
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def handle_fatal_error(error: BaseException) -> NoReturn:
    print(str(error))
    raise SystemExit(1)
