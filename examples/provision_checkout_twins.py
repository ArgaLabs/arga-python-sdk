"""Provision disposable integrations like Stripe for staging or QA."""

from __future__ import annotations

import os

from _shared import handle_fatal_error, print_json, require_env

from arga_sdk import Arga, TwinProvisionStatus

twin_setup = {
    "twins": ["stripe"],
    "ttl_minutes": 60,
    "poll_interval_seconds": 5.0,
    "timeout_seconds": 300.0,
}


def wait_for_ready(client: Arga, run_id: str) -> TwinProvisionStatus:
    return client.twin_runs.wait(
        run_id,
        poll_interval=twin_setup["poll_interval_seconds"],
        timeout=twin_setup["timeout_seconds"],
    )


def main() -> None:
    client_kwargs = {"api_key": require_env("ARGA_API_KEY")}
    base_url = os.environ.get("ARGA_BASE_URL")
    if base_url:
        client_kwargs["base_url"] = base_url

    with Arga(**client_kwargs) as client:
        provisioned = client.twin_runs.create(
            twin_setup["twins"],
            ttl_minutes=twin_setup["ttl_minutes"],
        )
        print_json("Provision request accepted", provisioned.model_dump(mode="json", exclude_none=True))

        status = wait_for_ready(client, provisioned.run_id)

        print_json(
            "Provisioning summary",
            {
                "run_id": status.run_id,
                "status": status.status,
                "dashboard_url": status.dashboard_url,
                "expires_at": status.expires_at,
            },
        )

        if status.status != "ready" or status.error is not None:
            failure = status.error
            if not failure and status.failure_detail:
                failure = f"{status.failure_detail.code}: {status.failure_detail.public_message}"
            raise RuntimeError(f"Twin provisioning failed: {failure or status.status}")

        if status.twins:
            for name, twin in status.twins.items():
                print_json(
                    f"{name} twin",
                    {
                        "base_url": twin.base_url,
                        "admin_url": twin.admin_url,
                        "env_vars": twin.env_vars,
                    },
                )

        print("\nCopy the env vars above into your staging or QA environment before running the dependent flow.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_fatal_error(exc)
