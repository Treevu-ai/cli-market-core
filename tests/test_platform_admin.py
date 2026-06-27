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
    monkeypatch.delenv("MARKET_API_TOKEN", raising=False)


def test_admin_username_not_platform_admin_without_ops_env():
    assert is_platform_admin("admin") is False


def test_admin_username_platform_admin_when_market_api_token_set(monkeypatch):
    monkeypatch.setenv("MARKET_API_TOKEN", "ops-secret")
    assert is_platform_admin("admin") is True


def test_market_admin_users_env(monkeypatch):
    monkeypatch.setenv("MARKET_ADMIN_USERS", "ceo-user,ops-user")
    assert is_platform_admin("ceo-user") is True
    assert is_platform_admin("random-user") is False


def test_user_can_checkout_platform_admin_user(monkeypatch):
    ensure_db_initialized()
    monkeypatch.setenv("MARKET_ADMIN_USERS", "founder-abc")
    assert user_can_checkout("founder-abc") is True


def test_user_can_checkout_admin_only_with_ops_env(monkeypatch):
    ensure_db_initialized()
    assert user_can_checkout("admin") is False
    monkeypatch.setenv("MARKET_API_TOKEN", "ops-secret")
    assert user_can_checkout("admin") is True


def test_db_get_subscription_admin_effective_enterprise(monkeypatch):
    ensure_db_initialized()
    monkeypatch.setenv("MARKET_API_TOKEN", "ops-secret")
    sub = db_get_subscription("admin")
    assert sub["tier"] == "enterprise"
    assert sub["req_limit_day"] == -1
    assert sub.get("platform_admin") is True
    assert sub["export"] is True
