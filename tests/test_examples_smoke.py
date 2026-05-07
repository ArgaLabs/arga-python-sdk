from __future__ import annotations

import importlib
import sys
from pathlib import Path


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
MODULE_NAMES = [
    "validate_staging_release",
    "create_checkout_scenario",
    "ensure_scenario_twin_urls",
    "provision_checkout_twins",
    "explore_staging_with_agent",
]


def test_examples_import_without_running() -> None:
    sys.path.insert(0, str(EXAMPLES_DIR))
    try:
        for module_name in MODULE_NAMES:
            module = importlib.import_module(module_name)
            assert hasattr(module, "main")
    finally:
        if str(EXAMPLES_DIR) in sys.path:
            sys.path.remove(str(EXAMPLES_DIR))

        for module_name in MODULE_NAMES + ["_shared"]:
            sys.modules.pop(module_name, None)
