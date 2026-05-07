from __future__ import annotations

import pytest
import respx

from arga_sdk import Arga, AsyncArga

TEST_BASE_URL = "https://test.argalabs.com"
TEST_API_KEY = "arga_test_key_1234567890"


@pytest.fixture()
def client() -> Arga:
    """Create a sync Arga client pointed at a test URL."""
    c = Arga(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    yield c
    c.close()


@pytest.fixture()
def async_client() -> AsyncArga:
    """Create an async Arga client pointed at a test URL."""
    c = AsyncArga(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    yield c


@pytest.fixture()
def mock_router() -> respx.Router:
    """Return a started respx mock router scoped to the test base URL."""
    with respx.mock(base_url=TEST_BASE_URL) as router:
        yield router


# --------------------------------------------------------------------------
# Shared mock response payloads
# --------------------------------------------------------------------------


RUN_RESPONSE = {
    "run_id": "run_abc123",
    "status": "running",
    "session_id": "sess_xyz",
}

RUN_DETAIL_RUNNING = {
    "id": "run_abc123",
    "run_id": "run_abc123",
    "status": "running",
    "run_type": "url_run",
    "mode": "quick",
    "environment_url": "https://staging.example.com",
    "surface_urls": ["https://staging.example.com/home"],
    "twins": ["stripe", "plaid"],
    "results_json": None,
    "event_log_json": None,
    "story_json": None,
    "attack_plan_json": None,
    "redteam_report_json": None,
    "step_summaries": None,
    "failure_category": None,
    "failure_detail": None,
    "created_at": "2026-03-15T10:30:00Z",
}

RUN_DETAIL_COMPLETED = {
    **RUN_DETAIL_RUNNING,
    "status": "completed",
    "results_json": {"tests": [{"name": "login", "passed": True}]},
    "story_json": {"summary": "All tests passed."},
}

TWIN_STRIPE = {
    "name": "stripe",
    "label": "Stripe Payments",
    "kind": "unified",
    "show_in_ui": True,
}

TWIN_PLAID = {
    "name": "plaid",
    "label": "Plaid Banking",
    "kind": "unified",
    "show_in_ui": True,
}

TWIN_PROVISION_STATUS = {
    "run_id": "run_abc123",
    "status": "ready",
    "twins": {
        "stripe": {
            "name": "stripe",
            "label": "Stripe Payments",
            "base_url": "https://twins.argalabs.com/stripe/run_abc123",
            "admin_url": "https://twins.argalabs.com/stripe/run_abc123/admin",
            "env_vars": {"STRIPE_API_KEY": "sk_test_twin_1234"},
            "show_in_ui": True,
        },
        "plaid": {
            "name": "plaid",
            "label": "Plaid Banking",
            "base_url": "https://twins.argalabs.com/plaid/run_abc123",
            "admin_url": None,
            "env_vars": {"PLAID_CLIENT_ID": "twin_client_id"},
            "show_in_ui": True,
        },
    },
    "dashboard_url": "https://app.argalabs.com/runs/run_abc123",
    "expires_at": "2026-03-15T11:30:00Z",
    "proxy_token": "proxy_tok_abc",
    "is_public": False,
    "error": None,
}

TWIN_PUBLIC_PROVISION_STATUS = {
    "run_id": "run_pub123",
    "status": "ready",
    "twins": {
        "slack": {
            "name": "slack",
            "label": "Slack",
            "base_url": "https://pub-r0123456789abcdef0123456789abcdef--slack.sandbox.argalabs.com",
            "admin_url": "https://r0123456789abcdef0123456789abcdef--slack.sandbox.argalabs.com",
            "env_vars": {"SLACK_BOT_TOKEN": "xoxb-twin-test"},
            "show_in_ui": True,
        },
    },
    "dashboard_url": "https://app.argalabs.com/runs/run_pub123",
    "expires_at": "2026-03-15T11:30:00Z",
    "proxy_token": "proxy_tok_pub",
    "is_public": True,
    "error": None,
}

SCENARIO_RESPONSE = {
    "id": "scn_abc123",
    "name": "Login Flow Test",
    "description": "Validates the login flow end-to-end",
    "prompt": "Test the login form with valid and invalid credentials",
    "twins": ["stripe"],
    "seed_config": {"users": [{"email": "test@example.com", "password": "secret"}]},
    "tags": ["auth", "login"],
    "created_at": "2026-03-01T09:00:00Z",
    "updated_at": "2026-03-10T14:00:00Z",
}

SCENARIO_TWIN_ENVIRONMENT_RESPONSE = {
    "id": "env_abc123",
    "scenario_id": "scn_abc123",
    "status": "ready",
    "requested_twins": ["stripe"],
    "twins": {
        "stripe": {
            "name": "stripe",
            "label": "Stripe",
            "base_url": "https://scn-0123456789abcdef0123456789abcdef--stripe.sandbox.argalabs.com",
            "admin_url": "https://r0123456789abcdef0123456789abcdef--stripe.sandbox.argalabs.com",
            "env_vars": {"STRIPE_API_KEY": "sk_test_twin"},
            "show_in_ui": True,
        }
    },
    "run_id": "run_abc123",
    "dashboard_url": "https://app.argalabs.com/runs/run_abc123",
    "proxy_token": "proxy_tok_abc",
    "public": True,
    "error": None,
    "seed_results": {"stripe": {"env_vars": {"STRIPE_API_KEY": "sk_test_twin"}}},
    "last_seeded_at": "2026-03-15T10:35:00Z",
    "created_at": "2026-03-15T10:30:00Z",
    "updated_at": "2026-03-15T10:35:00Z",
}
