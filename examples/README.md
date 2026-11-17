# SDK examples

Install the standard package with `pip install arga-py-sdk` or `uv add arga-py-sdk`.
It includes tracing and the Gmail/Stripe client dependencies. For this unreleased
v0.2.0 checkout, use `pip install -e '.[dev]'`.

Set `ARGA_API_KEY` securely before running a live example. If needed, set
`ARGA_BASE_URL` to another backend API URL; the default is `https://api.argalabs.com`.
Open each script and adjust its configuration before running it.

| Script | Workflow |
| --- | --- |
| [validate_staging_release.py](validate_staging_release.py) | Create and wait for a browser Test Run against an existing staging deployment; fail the release gate on an unsuccessful outcome |
| [create_checkout_scenario.py](create_checkout_scenario.py) | Save an explicit, reusable checkout Scenario |
| [provision_checkout_twins.py](provision_checkout_twins.py) | Create a Twin Run, wait for readiness and inspect its endpoints |
| [ensure_scenario_twin_urls.py](ensure_scenario_twin_urls.py) | Create or reuse a Scenario's persistent twin environment |
| [explore_staging_with_agent.py](explore_staging_with_agent.py) | Record a browser flow through the current Test Runs API; its historical filename is retained |

Run a configured script with:

```sh
uv run python examples/validate_staging_release.py
```

The application under test must already be reachable. If it needs service twins,
provision them first and configure your application with their endpoints. Passing
Twin Run or Scenario context to a browser Test Run does not deploy application code.
The current examples do not use the retired custom-code/agent-run creation workflow.

The SDK test suite imports every example without running live APIs. Tracing setup
and customer-hosted Braintrust sync are documented in the main [README](../README.md).
