"""Tests for platform admin billing bypass."""

import os

import pytest

from market_core import ensure_db_initialized
from market_core.market_billing import db_get_subscription, user_can_checkout
from market_core.platform_admin import is_platform_admin


@pytest.fixture(autouse=True)
def _clean_admin_env(monkeypatch):
    monkeypatch.delenv("MARKET_ADMIN_USERS", raising=False)
    monkeypatch.delenv("MARKET_ADMIN_API_KEYS", raising=False)


def test_admin_username_is_platform_admin():
    assert is_platform_admin("admin") is True


def test_market_admin_users_env():
    os.environ["MARKET_ADMIN_USERS"] = "ceo-user,ops-user"
    try:
        assert is_platform_admin("ceo-user") is True
        assert is_platform_admin("random-user") is False
    finally:
        del os.environ["MARKET_ADMIN_USERS"]


def test_user_can_checkout_platform_admin():
    ensure_db_initialized()
    assert user_can_checkout("admin") is True
    os.environ["MARKET_ADMIN_USERS"] = "founder-abc"
    try:
        assert user_can_checkout("founder-abc") is True
    finally:
        del os.environ["MARKET_ADMIN_USERS"]


def test_db_get_subscription_admin_effective_enterprise():
    ensure_db_initialized()
    sub = db_get_subscription("admin")
    assert sub["tier"] == "enterprise"
    assert sub["req_limit_day"] == -1
    assert sub.get("platform_admin") is True
    assert sub["export"] is True
