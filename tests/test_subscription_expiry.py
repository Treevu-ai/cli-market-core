"""Tests for subscription expires_at handling (referral-granted temporary tiers)."""

import uuid

from market_core import ensure_db_initialized
from market_core.market_billing import db_get_subscription, db_set_subscription


def _unique_username() -> str:
    return f"expiry-test-{uuid.uuid4().hex[:12]}"


def test_temporary_grant_active_before_expiry():
    ensure_db_initialized()
    username = _unique_username()
    db_set_subscription(username, "pro", expires_days=30)
    sub = db_get_subscription(username)
    assert sub["tier"] == "pro"
    assert sub["expires_at"] is not None


def test_temporary_grant_falls_back_to_free_after_expiry():
    ensure_db_initialized()
    username = _unique_username()
    # expires_days=-1 backdates expires_at into the past, simulating an
    # already-expired referral-granted free Pro month.
    db_set_subscription(username, "pro", expires_days=-1)
    sub = db_get_subscription(username)
    assert sub["tier"] == "free"
    assert sub["req_limit_day"] == 1000
    assert sub["req_limit_min"] == 60


def test_permanent_grant_has_no_expiry():
    ensure_db_initialized()
    username = _unique_username()
    db_set_subscription(username, "pro")
    sub = db_get_subscription(username)
    assert sub["tier"] == "pro"
    assert sub["expires_at"] is None


def test_permanent_grant_clears_prior_temporary_expiry():
    ensure_db_initialized()
    username = _unique_username()
    db_set_subscription(username, "pro", expires_days=30)
    db_set_subscription(username, "pro")
    sub = db_get_subscription(username)
    assert sub["expires_at"] is None
