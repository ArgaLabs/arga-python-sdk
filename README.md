# Arga Python SDK

Typed Python client for the [Arga](https://argalabs.com) API. Supports both synchronous and asynchronous usage.

## Installation

Install with `uv`:

```bash
uv add arga-py-sdk
```

Or, if you're using `pip`:

```bash
pip install arga-py-sdk
```

## Quick Start

```python
from arga_sdk import Arga

client = Arga(api_key="arga_...")

# Create a URL run with service twins
run = client.runs.create_url_run(
    url="https://staging.myapp.com",
    twins=["stripe", "slack"],
)
print(run.run_id, run.status)

# Poll until the run completes
detail = client.runs.wait(run.run_id, timeout=300)
print(detail.status, detail.results_json)

# Stream live results
for event in client.runs.stream_results(run.run_id):
    print(event)

# Cancel a run
client.runs.cancel(run.run_id)
```

## Async Usage

```python
import asyncio
from arga_sdk import AsyncArga

async def main():
    client = AsyncArga(api_key="arga_...")

    run = await client.runs.create_url_run(url="https://staging.myapp.com")

    # Stream results
    async for event in client.runs.stream_results(run.run_id):
        print(event)

    # Wait for completion
    detail = await client.runs.wait(run.run_id)
    print(detail.status)

    await client.close()

asyncio.run(main())
```

## Context Manager

Both clients support context managers to ensure proper cleanup:

```python
with Arga(api_key="arga_...") as client:
    run = client.runs.create_url_run(url="https://staging.myapp.com")

async with AsyncArga(api_key="arga_...") as client:
    run = await client.runs.create_url_run(url="https://staging.myapp.com")
```

## Available Methods

### Runs

| Method | Description |
|--------|-------------|
| `client.runs.create_url_run(url, ...)` | Test a live URL with browser validation |
| `client.runs.create_pr_run(repo, ...)` | Validate code changes from a PR or branch |
| `client.runs.create_agent_run(...)` | Deploy an autonomous agent for exploration |
| `client.runs.get(run_id)` | Get full run details |
| `client.runs.stream_results(run_id)` | Stream SSE result events |
| `client.runs.cancel(run_id)` | Cancel a running run |
| `client.runs.wait(run_id, ...)` | Poll until terminal status |

### Twins

| Method | Description |
|--------|-------------|
| `client.twins.list()` | List available service twins |
| `client.twins.provision(twins, ...)` | Provision twin instances |
| `client.twins.get_status(run_id)` | Get provisioning status |
| `client.twins.extend(run_id, ...)` | Extend twin TTL |

### Scenarios

| Method | Description |
|--------|-------------|
| `client.scenarios.create(name, ...)` | Create a test scenario |
| `client.scenarios.list(...)` | List scenarios (with optional filters) |
| `client.scenarios.get(scenario_id)` | Get a scenario by ID |

## Error Handling

```python
from arga_sdk import Arga, ArgaAPIError, ArgaError

client = Arga(api_key="arga_...")

try:
    run = client.runs.get("nonexistent-id")
except ArgaAPIError as e:
    print(e.status_code)  # e.g. 404
    print(e.message)
except ArgaError as e:
    print(e.message)
```

## Documentation

Full API documentation is available at [docs.argalabs.com](https://docs.argalabs.com).
