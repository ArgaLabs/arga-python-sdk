# Examples

These examples are meant to look like small scripts a customer could adapt for a
release checklist, a QA handoff, or a staging workflow. They are not generic
CLI demos.

Install the package in your own project with `uv add arga-py-sdk`, or run the
examples directly from this repository with `uv run`.

## Prerequisites

Set your API key before running any live example:

```bash
export ARGA_API_KEY=arga_your_api_key
```

If you need a non-default environment, set:

```bash
export ARGA_BASE_URL=https://app.argalabs.com
```

## How To Use These Examples

Each example has a small config block near the top of the file. Before you run
one, open the file and edit that config to match your environment and flow.

Then run it from the repo root with `uv`:

```bash
uv run python examples/validate_staging_release.py
```

## Start Here

Start with `validate_staging_release.py` if you are new to the SDK. It is the
best first example because it matches a common customer question: “Can I gate a
release on a staging validation run?”

## Customer Workflows

### How do I validate staging before a release?

Use [`validate_staging_release.py`](validate_staging_release.py).

Before running it, edit the `release_validation` config block near the top of
the file so it points at your staging or RC URL and the flow you actually care
about.

```bash
uv run python examples/validate_staging_release.py
```

What it does:

- creates a URL validation run against staging
- waits for Arga to finish
- prints a concise release-gate summary
- exits non-zero if the run does not finish cleanly

### How do I create a reusable checkout scenario?

Use [`create_checkout_scenario.py`](create_checkout_scenario.py).

Before running it, edit the `checkout_scenario` config block so the prompt,
tags, and seed data match your product.

```bash
uv run python examples/create_checkout_scenario.py
```

What it does:

- creates a reusable scenario for a business-critical checkout flow
- stores realistic seed data and scenario metadata
- prints the created scenario ID so your team can reuse it later

### How do I provision disposable dependencies like Stripe?

Use [`provision_checkout_twins.py`](provision_checkout_twins.py).

Before running it, edit the `twin_setup` config block to match the integrations
your app depends on.

```bash
uv run python examples/provision_checkout_twins.py
```

What it does:

- provisions disposable twins for external dependencies
- waits until those twins are ready
- prints dashboard URLs, endpoints, and env vars in a copyable shape

### How do I keep stable twin URLs for a scenario?

Use [`ensure_scenario_twin_urls.py`](ensure_scenario_twin_urls.py).

Before running it, set `ARGA_SCENARIO_ID` to the saved scenario that should own
the long-lived twin environment.

```bash
ARGA_SCENARIO_ID=scn_... uv run python examples/ensure_scenario_twin_urls.py
```

What it does:

- creates or returns the scenario's always-on twin environment
- prints each permanent twin `base_url`
- leaves disposable `client.twins.provision()` workflows unchanged

### How do I let Arga explore staging autonomously?

Use [`explore_staging_with_agent.py`](explore_staging_with_agent.py).

Before running it, edit the `agent_run` config block so the objective matches
what your team wants explored on staging.

```bash
uv run python examples/explore_staging_with_agent.py
```

What it does:

- launches an autonomous agent run against staging
- waits for the run to finish
- prints the high-signal artifacts you would review before acting on the build

## Validation

The repo includes a smoke test that imports these examples without executing
live API calls:

```bash
uv run pytest
```
