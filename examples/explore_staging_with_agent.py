"""Record a browser flow against a reachable staging app using current Test Runs.

The historical filename is retained; this does not deploy customer agent code.
"""

from __future__ import annotations

import os

from _shared import handle_fatal_error, print_json, require_env

from arga_sdk import Arga

agent_run = {
    "url": os.environ.get("STAGING_URL", "https://staging.example.com"),
    "focus": (
        "Explore onboarding, sign in, and the first purchase flow. Look for "
        "dead ends, broken states, and obvious regressions."
    ),
    "poll_interval_seconds": 2.5,
    "timeout_seconds": 600.0,
}


def main() -> None:
    client_kwargs = {"api_key": require_env("ARGA_API_KEY")}
    base_url = os.environ.get("ARGA_BASE_URL")
    if base_url:
        client_kwargs["base_url"] = base_url

    with Arga(**client_kwargs) as client:
        run = client.test_runs.create(
            start_url=agent_run["url"],
            prompt=agent_run["focus"],
        )
        print_json("Created browser Test Run", run.model_dump(mode="json", exclude_none=True))

        detail = client.test_runs.wait(
            run.id,
            poll_interval=agent_run["poll_interval_seconds"],
            timeout=agent_run["timeout_seconds"],
        )

        print_json(
            "Browser flow summary",
            {
                "run_id": run.id,
                "status": detail.status,
                "mode": detail.mode,
                "start_url": detail.start_url,
                "error_message": detail.error_message,
            },
        )

        if detail.summary_json is not None:
            print_json("summary_json", detail.summary_json)
        if detail.test_config_json is not None:
            print_json("Editable TestConfig", detail.test_config_json)

        if detail.status != "completed":
            raise RuntimeError(
                "The browser Test Run did not complete successfully. Review the "
                "artifacts above before acting on the environment."
            )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_fatal_error(exc)
