"""Create a reusable checkout scenario for a business-critical flow."""

from __future__ import annotations

import os

from arga_sdk import Arga

from _shared import handle_fatal_error, print_json, require_env

checkout_scenario = {
    "name": "Checkout Upgrade Flow",
    "description": (
        "Reusable scenario for validating the returning-user upgrade and "
        "checkout flow."
    ),
    "prompt": (
        "Sign in as a returning customer, upgrade from Starter to Pro, "
        "complete checkout with Stripe, and verify the confirmation screen "
        "and subscription state."
    ),
    "twins": ["stripe"],
    "tags": ["checkout", "release-gate"],
    "seed_config": {
        "user": {
            "email": "qa-buyer@example.com",
            "is_returning_customer": True,
        },
        "account": {
            "current_plan": "starter",
        },
        "cart": {
            "items": [{"sku": "pro-monthly", "quantity": 1}],
        },
    },
}


def main() -> None:
    client_kwargs = {"api_key": require_env("ARGA_API_KEY")}
    base_url = os.environ.get("ARGA_BASE_URL")
    if base_url:
        client_kwargs["base_url"] = base_url

    with Arga(**client_kwargs) as client:
        scenario = client.scenarios.create(
            checkout_scenario["name"],
            prompt=checkout_scenario["prompt"],
            seed_config=checkout_scenario["seed_config"],
            twins=checkout_scenario["twins"],
            description=checkout_scenario["description"],
            tags=checkout_scenario["tags"],
        )

        print_json("Created scenario", scenario.model_dump(mode="json", exclude_none=True))
        print(
            f"\nSaved scenario {scenario.id}. Reuse this scenario in future "
            "validation or QA workflows."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_fatal_error(exc)
