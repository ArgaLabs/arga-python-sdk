"""Ensure long-lived twin URLs for a saved scenario."""

from __future__ import annotations

import os

from arga_sdk import Arga, ArgaAPIError

from _shared import handle_fatal_error, print_json, require_env

scenario_twin_urls = {
    # Create this with create_checkout_scenario.py or your own scenario setup.
    "scenario_id": os.environ.get("ARGA_SCENARIO_ID", "replace-with-scenario-id"),
    # Leave empty to use the twins saved on the scenario.
    "twins": ["stripe", "slack"],
}


def main() -> None:
    client = Arga(
        api_key=require_env("ARGA_API_KEY"),
        base_url=os.environ.get("ARGA_BASE_URL", "https://app.argalabs.com"),
    )
    try:
        env = client.scenarios.ensure_twin_environment(
            scenario_twin_urls["scenario_id"],
            twins=scenario_twin_urls["twins"],
            public=True,
        )
        print_json("Permanent scenario twin environment", env.model_dump(mode="json"))
        if env.twins:
            for name, twin in env.twins.items():
                print(f"{name}: {twin.base_url}")
    except (ArgaAPIError, RuntimeError) as exc:
        handle_fatal_error(exc)
    finally:
        client.close()


if __name__ == "__main__":
    main()
