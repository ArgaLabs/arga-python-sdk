# Arga Python SDK

Python client for Arga's Twin Runs, Saved Tests, browser Test Runs, Scenarios and
Training APIs, with synchronous and asynchronous clients. Customer-side tracing
and its Gmail/Stripe dependencies are included in the standard package.

## Installation

```sh
pip install arga-py-sdk
# or
uv add arga-py-sdk
```

These additions are in v0.2.0, which must be released before the commands above
install them. During development use `pip install -e '.[dev]'` from this checkout.
Python 3.10 or later is required. Installing or importing the SDK does not enable
tracing; collection starts only when explicitly configured in your application.

The default API URL is `https://api.argalabs.com`. The dashboard is
`https://app.argalabs.com`. Pass `base_url` explicitly for another API environment.

## Run a browser test

```python
import os
from arga_sdk import Arga

with Arga(api_key=os.environ["ARGA_API_KEY"]) as client:
    run = client.test_runs.create(
        prompt="Sign in, open billing, and verify the checkout flow.",
        start_url="https://staging.example.com",
    )
    result = client.test_runs.wait(run.id, timeout=600)
    print(result.status, result.summary_text)

    # Save the recorded, editable TestConfig for reuse after inspecting it.
    if result.status == "completed" and result.test_config_json:
        test = client.tests.create("Checkout regression", run_id=result.id)
        rerun = client.tests.run(test.id, start_url="https://preview.example.com")
```

Test Runs execute browser flows against an already reachable application. Provision
twins separately and configure your application with their endpoints before testing.
The Test Run's `twins`, `scenario_id`, repository and PR fields record context; they
do not deploy application code or automatically provision services.

## Provision twins

```python
with Arga(api_key=os.environ["ARGA_API_KEY"]) as client:
    run = client.twin_runs.create(
        ["gmail", "stripe"], ttl_minutes=60, public=False,
        scenario_prompt="A support mailbox with a duplicate payment needing review.",
        scenario_generation_mode="thorough",
    )
    status = client.twin_runs.wait(run.run_id)
    if status.status == "ready":
        stripe_url = status.twins["stripe"].base_url
        # Configure your application with returned endpoints and credentials.
    client.twin_runs.teardown(run.run_id)
```

Creating a Twin Run returns an accepted `run_id`; poll `get` or `wait` for state,
progress, endpoints and any structured failure. `wait` returns terminal failures
too, so inspect its status. Limits and access checks remain enforced by the backend.
`public=False` requires the returned proxy credential when calling private surfaces.

## Async usage

Every resource operation has the same interface on `AsyncArga`:

```python
from arga_sdk import AsyncArga

async def check_release():
    async with AsyncArga(api_key=os.environ["ARGA_API_KEY"]) as client:
        run = await client.test_runs.create(
            "Verify checkout", start_url="https://staging.example.com",
        )
        return await client.test_runs.wait(run.id)
```

## Current resource methods

| Namespace | Operations |
| --- | --- |
| `client.twins` | `list()` retrieves the current twin catalog |
| `client.twin_runs` | `create`, `get`, `wait`, `extend`, `reset`, `lock`, `teardown`, `microsoft_scenario_snapshot` |
| `client.tests` | `create`, `list`, `get`, `update`, `delete`, `run` |
| `client.test_runs` | `create`, `list`, `get`, `rerun`, `update_config`, `send_message`, `artifact_url`, `wait` |
| `client.scenarios` | `create`, `list`, `get`, `update`, `copy`, `delete`, `list_presets`, `get_preset`, `list_long_runs`; existing environment methods |
| `client.training` | `create_upload_key`, `upload_evidence`, `list`, `get`, `generate_task`, `update_task`, `review_task`, `prepare_grader`, `get_grader`, `test_grader`, `create_environment`, `export_jsonl` |

List methods return Python lists, unwrapping the backend's Saved Test/Test Run
response envelopes. `tests.list(repo_full_name=...)` filters by repository.
`scenarios.list` supports `twin`, `tag`, `scope`, `include_presets`, `search`,
`limit` and `offset`. Scenario creation supports personal/workspace scope and
Fast/Thorough generation. Scenario environment creation also accepts
`github_actions_mode`; Twin Runs additionally accept `access_profile`.

Updates preserve omitted fields and explicit nulls separately:

```python
client.tests.update(test_id, description=None, repo_full_name=None, ci_enabled=False)
client.scenarios.update(scenario_id, description=None, tags=[])
```

`artifact_url(run_id, filename)` returns the backend's signed storage URL without
forwarding the Arga credential to storage. Fetch that URL separately if needed.
Run events are available in `test_runs.get(run_id).events_json`; the backend's
browser WebSocket stream requires a session JWT and is not exposed as an API-key
SSE stream. `test_runs.list()` currently returns the backend's latest 25 runs.
Reset uses the backend's existing `/validate/twins/provision/{id}/reset` route;
the other Twin Run lifecycle methods use `/twin-runs`.

The older `client.runs.*` and twin provision/status helpers remain available for
compatibility. New integrations should use the current resource methods above.
Historical custom-code/agent deployment is not a current SDK quickstart workflow.

## Training review

Agent processes should hold a source-bound upload key and send locally filtered
evidence. An authenticated control-plane client can then inspect and prepare tasks:

```python
dataset = client.training.get(dataset_id)
task = client.training.generate_task(dataset.id, trace_id=dataset.traces[0]["id"])
grader = client.training.get_grader(dataset.id, task.id)
# Review the task, assumptions, starting state and grader before approving it.
```

Task edits and review calls require the current revision. Approval requires explicit
assumption and grader acknowledgements. `export_jsonl` returns approved task records
as the backend's JSONL text, preserving provenance and grader artifacts. Environment
creation provisions reviewed Scenario twins; it does not host customer agents or train
models. Upload-only credentials cannot perform these administrative operations.
Generation can take several minutes; configure `Arga(timeout=300)` or
`AsyncArga(timeout=300)` for task generation or Thorough scenario generation.

## Examples and errors

Runnable workflows are in [examples/README.md](examples/README.md). Configure your
application and credentials before running a live example; tests use mocked transports.

```python
from arga_sdk import ArgaAPIError, ArgaError

try:
    result = client.test_runs.get(run_id)
except ArgaAPIError as error:
    print(error.status_code, error.message)
```

## Customer-side tracing for Training

The v0.2 tracing module collects selected Gmail/Stripe evidence for Arga Training.
Selection, identity aliases and text filtering run in your process. Provider API keys,
headers, arbitrary metadata, model prompts/reasoning, raw MIME and attachments are not
exported. Free text is disabled until you explicitly select fields.

Install the standard package, including tracing and the Gmail/Stripe client libraries:

```sh
pip install arga-py-sdk
```

This version must be released before that command installs v0.2. For development,
install this checkout with `pip install -e '.[dev]'`.

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
and makes up to three attempts for transient failures. There is no disk spool; exhausted retries,
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

The shared JSON Schema checks resource/provider agreement, resource-specific fields,
and record types and labels. Runtime validation additionally requires contiguous event
sequence numbers. Braintrust sync accepts concurrent reads; overlapping reads/writes
remain a coverage gap because their starting state is ambiguous. Malformed trace trees
stay in the private checkpoint for retry while healthy roots continue; `coverage_gaps`
reports their count for the current window. Pending roots are bounded to 1,000.
