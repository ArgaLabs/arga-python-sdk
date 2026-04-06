"""Validate staging before a release and block on failed results."""

from __future__ import annotations

import os

from arga_sdk import Arga

from _shared import handle_fatal_error, print_json, require_env

release_validation = {
    "url": os.environ.get("STAGING_URL", "https://staging.example.com"),
    "twins": ["stripe"],
    "prompt": (
        "Validate sign in, the upgrade flow, and checkout before this "
        "release goes live."
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
        print(
            f"Creating a release-gate run for {release_validation['url']}..."
        )

        run = client.runs.create_url_run(
            url=release_validation["url"],
            prompt=release_validation["prompt"],
            twins=release_validation["twins"],
        )
        print_json("Created run", run.model_dump(mode="json", exclude_none=True))

        detail = client.runs.wait(
            run.run_id,
            poll_interval=release_validation["poll_interval_seconds"],
            timeout=release_validation["timeout_seconds"],
        )

        print_json(
            "Release gate summary",
            {
                "run_id": run.run_id,
                "status": detail.status,
                "run_type": detail.run_type,
                "environment_url": detail.environment_url,
                "failure_category": detail.failure_category,
                "failure_detail": detail.failure_detail,
            },
        )

        if detail.results_json is not None:
            print_json("results_json", detail.results_json)
        if detail.story_json is not None:
            print_json("story_json", detail.story_json)

        release_blocked = (
            detail.status != "completed"
            or detail.failure_category is not None
            or detail.failure_detail is not None
        )
        if release_blocked:
            raise RuntimeError(
                "Release validation did not finish cleanly. Review the Arga "
                "output above before shipping."
            )

        print("\nRelease validation passed. This environment looks ready.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_fatal_error(exc)
