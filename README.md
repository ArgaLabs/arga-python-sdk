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
    twins=["stripe", "slack", "salesforce", "waterfall"],
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

## Examples

Runnable examples live in [`examples/`](examples/README.md). They are the best
way to see realistic customer workflows end to end.

Before running any example, set your API key:

```bash
export ARGA_API_KEY=arga_your_api_key
```

If you need a non-default API environment, you can also set:

```bash
export ARGA_BASE_URL=https://app.argalabs.com
```

Start with the staging validation example:

```bash
uv run python examples/validate_staging_release.py
```

Each example is a small workflow script with an editable config block near the
top of the file. Open the file, adjust the business-specific values, then run
it with `uv`.

Choose an example based on the customer job you want to model:

- [`examples/validate_staging_release.py`](examples/validate_staging_release.py): validate staging before a release
- [`examples/create_checkout_scenario.py`](examples/create_checkout_scenario.py): create a reusable checkout scenario
- [`examples/ensure_scenario_twin_urls.py`](examples/ensure_scenario_twin_urls.py): ensure stable scenario twin URLs
- [`examples/provision_checkout_twins.py`](examples/provision_checkout_twins.py): provision disposable integrations like Stripe or Salesforce
- [`examples/explore_staging_with_agent.py`](examples/explore_staging_with_agent.py): let Arga explore staging autonomously

See [`examples/README.md`](examples/README.md) for exact commands, required
edits, and expected output for each example.

## Available Methods

### Runs

| Method | Description |
|--------|-------------|
| `client.runs.create_url_run(url, ...)` | Test a live URL with browser validation |
| `client.runs.create_pr_run(repo, ...)` | Validate code changes from a PR or branch |
| `client.runs.create_agent_run(repo, ...)` | Deploy an autonomous agent for PR or branch exploration |
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
| `client.scenarios.ensure_twin_environment(scenario_id, ...)` | Create or return permanent twin URLs for a scenario |
| `client.scenarios.get_twin_environment(scenario_id)` | Get permanent twin environment status and URLs |
| `client.scenarios.reseed_twin_environment(scenario_id)` | Reseed a permanent twin environment from the scenario |
| `client.scenarios.delete_twin_environment(scenario_id)` | Tear down a permanent twin environment |
| `client.scenarios.list_twin_environments()` | List permanent scenario twin environments |

## Scenario generation modes

```python
scenario = client.scenarios.create(
    name="Support escalation",
    prompt="A Slack support channel with linked escalation threads and consistent message authors",
    generation_mode="thorough",
)
```

Fast is the default for everyday scenarios. Thorough handles complex requirements with a longer wait. Explicit `seed_config` bypasses generation. Import `ScenarioGenerationMode` from `arga_sdk` for typed helpers.

### Generate seed data from a prompt

```python
result = client.twins.provision(
    twins=["slack"],
    scenario_prompt="A support channel with linked escalation threads and consistent message authors",
    scenario_generation_mode="thorough",
)
run_id = result["run_id"]
```

Use `scenario_generation_mode="fast"` for everyday scenarios, or omit it to use the server's Fast default. Thorough handles complex requirements with a longer wait. A `scenario_id` takes precedence and reuses saved seed data. These options work with both `Arga` and `AsyncArga`; await calls on the async client.

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

## Customer-side tracing for Training

The v0.2 tracing module collects selected Gmail/Stripe evidence for Arga Training.
Selection, identity aliases and text filtering run in your process. Provider API keys,
headers, arbitrary metadata, model prompts/reasoning, raw MIME and attachments are not
exported. Free text is disabled until you explicitly select fields.

Install the optional provider libraries if your application does not already have them:

```sh
pip install 'arga-py-sdk[tracing]'
```

This version must be released before that command installs v0.2. For development,
install this checkout with `pip install -e '.[dev,tracing]'`.

Create a source-bound upload key once, outside your agent process, using a full Arga
credential. Store the returned secret in your own secret manager as `ARGA_TRACE_KEY`:

```python
import os
from arga_sdk import Arga

with Arga(api_key=os.environ["ARGA_API_KEY"], base_url="https://api.argalabs.com") as arga:
    credential = arga.training.create_upload_key(source="support-agent")
    upload_secret = credential.key.get_secret_value()  # Store securely; do not log.
```

Upload keys expire after 30 days, accept evidence only for their source, and cannot
read datasets, generate tasks, approve tasks or provision environments. Rotating the
account's legacy API key or revoking its sessions invalidates these upload keys.
There is no individual upload-key revocation list in v1; use short operational
rotation and the account-wide controls when needed.

Wrap your existing provider clients once, then wrap the agent entry point:

```python
from arga_sdk.tracing import CapturePolicy, init

tracing = init(
    source="support-agent",
    # ARGA_TRACE_KEY is read from the environment. No provider credentials go to Arga.
    policy=CapturePolicy(
        text_fields=frozenset({"goal", "policy", "gmail.subject", "gmail.body"}),
        revision="support-v1",
        # Add transform_text=your_local_filter for names and proprietary content.
    ),
)
stripe_client = tracing.wrap_stripe(existing_stripe_client)
gmail_service = tracing.wrap_gmail(existing_gmail_service)
# Configure your existing agent to use these wrapped clients.

@tracing.agent(
    goal=lambda request: request["task"],
    policies=["Customer confirmations require the accountable owner's review before sending."],
)
async def handle(request):
    return await existing_agent.run(request)

# During graceful shutdown, after agent work finishes:
# await tracing.aflush(timeout=5)
# tracing.close()
```

The `existing_*` names represent your application objects. No global library patches,
code scanning, framework prompt capture or extra provider requests occur. Only calls
made through wrapped clients inside an active episode are observed. Sync Stripe calls,
Stripe `*_async` methods, modern `StripeClient.v1` services and legacy Stripe resources
are supported. Gmail observes discovery-client requests when `.execute()` is called.
Batch requests, implicit auto-pagination, streaming/generator lifetimes, other providers
and arbitrary custom tools need additional adapters; do not assume these are captured.
Use `with tracing.episode(goal=..., policies=[...]):` around generator consumption.
Unknown executed operations and overlapping calls become explicit coverage gaps.

Selected text is still potentially sensitive business information. Built-in masking
replaces recognized emails, Stripe IDs and common credential formats; it does not
reliably detect people's names, every secret format, or proprietary facts. Supply a
local `transform_text` callback or export only locally extracted task facts for stronger
requirements. The callback runs before built-in masking and must not send raw data to
Arga or another service without your authorization. Bump `revision` when its behavior
changes. A filter exception drops the affected evidence and blocks generation.

For a completely local preview, set `upload=False` and inspect `tracing.last_episode`
after a run, or `episode.preview()` inside an explicit episode. Preview does not send
network requests. `tracing.recent_uploads()` returns bounded dataset receipts linking
to `/training/{dataset_id}`. `tracing.diagnostics()` returns content-free queued,
uploaded, dropped and failed counts. `flush()`/`aflush()` report queue drainage, not
guaranteed upload success; check those counters. Export uses a bounded in-memory queue
and retries transient failures three times. There is no disk spool; exhausted retries,
queue overflow and abrupt process termination can lose evidence. Shutdown does not
delay the agent indefinitely. Call `close()` after flushing to release exporter resources.

Each completed episode becomes one private Training collection. Identical payloads
deduplicate per owner; changed source evidence creates a separate immutable collection.
Tasks remain drafts until reviewed, with the existing assumptions and grader
acknowledgements. This prepares tasks, verifiers and twin environments; it does not
execute customer agents or train models in Arga. Uploaded evidence is retained by the
existing Training dataset storage and selected for Arga's configured generation model
when you request generation; v1 adds no automatic evidence expiry or retention policy.

### Braintrust sync in your infrastructure

Run the sync worker in your own Linux/macOS host or container. Both credentials stay
there. Arga receives only the same `arga.evidence.v1` projection used by the live SDK.
The worker does not use Arga's older server-side Braintrust import endpoint.

Create a local `trace-policy.json`:

```json
{
  "revision": "support-v1",
  "text_fields": ["goal", "policy", "gmail.subject", "gmail.body"],
  "goal_pointer": "/input/task",
  "policies": ["Customer confirmations require owner review before sending."],
  "operations": {
    "fetch_charge": "stripe.charges.retrieve",
    "issue_refund": "stripe.refunds.create",
    "read_message": "gmail.messages.get"
  }
}
```

The goal pointer selects a **string** from the root span; use `/input` if the root's
input is already a task string. Only select the policy excerpts you intend to share.
Mappings identify executed tool spans. Their `input` must contain provider arguments
and `output` must contain a provider-shaped response. Canonical names such as
`stripe.charges.retrieve` need no mapping. LLM/score/eval spans are ignored, including
their tool-call suggestions. A wrapper that stores responses under another object
must normalize those locally before using `project_trace`; v1 does not guess shapes.

With `BRAINTRUST_API_KEY` (project read access) and `ARGA_TRACE_KEY` set securely:

```sh
python -m arga_sdk.tracing sync \
  --source support-agent --project YOUR_BRAINTRUST_PROJECT_UUID \
  --state /var/lib/arga/braintrust-state.json \
  --since 2026-11-17T00:00:00+00:00 --policy ./trace-policy.json --watch
```

Without `--watch`, one window is processed. The watcher processes bounded five-minute
windows, re-reads two minutes of overlap and waits 30 seconds when caught up. Complete
span trees are retrieved even when children fall outside the root's window. Each query
is capped at 2 MB/1,000 records; dense sources should use smaller windows through the
`BraintrustSync` Python API. A missing parent, conflicting revision, repeated pagination
cursor, invalid response or unacknowledged upload prevents checkpoint advancement.
`metrics.start`/`metrics.end` must establish completed, non-overlapping tool calls;
missing or ambiguous timing is uploaded as incomplete evidence and cannot generate tasks.

Unfinished roots stay in a bounded pending set and are revisited even after leaving
the overlap window; their changing partial payloads are not uploaded. The checkpoint
is atomically written with mode 0600 and locked against concurrent workers. It contains
the local alias key, pending root references and acknowledgement hashes, not API keys
or span payloads. Preserve it across restarts; protect it like other customer-local secrets.
The cache is scoped to the source, project, policy, initial start and Arga destination/
account. A scoped-key renewal for the same account preserves compatibility. Use a new
checkpoint when changing those settings. Late spans beyond the configured overlap
require an intentional backfill; sync is not a lossless production audit log.

For custom local text filtering, instantiate `BraintrustSync(policy=CapturePolicy(...,
transform_text=your_filter), ...)` in Python instead of the JSON-only CLI.

### Evidence contract and coverage

The shared fixtures and JSON Schema are in `tests/fixtures/`. Gmail projections retain
aliased message/thread identities, selected sender/recipient addresses, labels and
dates; selected subject/plain-text body fields are opt-in. Stripe projections retain
aliased customer/payment/charge/refund relationships, amounts, currency, status and
relevant payment/refund state. Names, billing details, query strings, arbitrary request
options, custom metadata, MIME and attachments are omitted. Aliases are consistent
within an episode and cannot be reversed using data uploaded to Arga.

Limits are 100 KB/episode, 100 operations and 50 records/operation. Limits do not
silently truncate critical evidence: coverage flags block task generation. `complete`
applies to a selected resource or returned page, never the whole production account.
Missing fields are unknown. Starting-state reconstruction remains partial, and generated
assumptions require review. No automatic production snapshot or permission-grant
enumeration is performed in v1; do not infer unobserved permissions from a successful call.

## Documentation

Full API documentation is available at [docs.argalabs.com](https://docs.argalabs.com).
