"""Let Arga explore staging autonomously with a focused objective."""

from __future__ import annotations

import os

from arga_sdk import Arga

from _shared import handle_fatal_error, print_json, require_env

agent_run = {
    "url": os.environ.get("STAGING_URL", "https://staging.example.com"),
    "focus": (
        "Explore onboarding, sign in, and the first purchase flow. Look for "
        "dead ends, broken states, and obvious regressions."
    ),
    "action_budget": 80,
    "poll_interval_seconds": 2.5,
    "timeout_seconds": 600.0,
}


def main() -> None:
    client_kwargs = {"api_key": require_env("ARGA_API_KEY")}
    base_url = os.environ.get("ARGA_BASE_URL")
    if base_url:
        client_kwargs["base_url"] = base_url

    with Arga(**client_kwargs) as client:
        run = client.runs.create_agent_run(
            url=agent_run["url"],
            focus=agent_run["focus"],
            action_budget=agent_run["action_budget"],
        )
        print_json("Created agent run", run.model_dump(mode="json", exclude_none=True))

        detail = client.runs.wait(
            run.run_id,
            poll_interval=agent_run["poll_interval_seconds"],
            timeout=agent_run["timeout_seconds"],
        )

        print_json(
            "Agent exploration summary",
            {
                "run_id": run.run_id,
                "status": detail.status,
                "run_type": detail.run_type,
                "environment_url": detail.environment_url,
                "failure_category": detail.failure_category,
                "failure_detail": detail.failure_detail,
            },
        )

        if detail.story_json is not None:
            print_json("story_json", detail.story_json)
        if detail.results_json is not None:
            print_json("results_json", detail.results_json)
        if detail.attack_plan_json is not None:
            print_json("attack_plan_json", detail.attack_plan_json)
        if detail.redteam_report_json is not None:
            print_json("redteam_report_json", detail.redteam_report_json)

        if detail.status != "completed":
            raise RuntimeError(
                "The agent run did not complete successfully. Review the "
                "artifacts above before acting on the environment."
            )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_fatal_error(exc)
