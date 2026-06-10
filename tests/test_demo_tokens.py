"""Tests for demo session tokens."""

from __future__ import annotations

import pytest

from market_core import ensure_db_initialized
from market_core.demo_tokens import (
    consume_demo_request,
    issue_demo_token,
    is_demo_token,
    is_demo_username,
    validate_demo_token,
)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "demo_test.db"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr("market_core.market_core.DB_FILE", db_file)
    monkeypatch.setattr("market_core.market_core.USE_PG", False)
    monkeypatch.setattr("market_core.market_core._pg_fell_back", False)
    monkeypatch.setattr("market_core.market_core._db_initialized", False)
    ensure_db_initialized()
    yield db_file


def test_issue_and_validate_demo_token(isolated_db):
    issued = issue_demo_token(client_ip="127.0.0.1", fingerprint="fp-test", max_requests=5)
    token = issued["demo_token"]
    assert is_demo_token(token)
    assert issued["requests_remaining"] == 5
    row = validate_demo_token(token)
    assert row is not None
    assert row["session_id"] == issued["session_id"]


def test_consume_demo_request_decrements_quota(isolated_db):
    issued = issue_demo_token(client_ip="10.0.0.1", max_requests=2)
    token = issued["demo_token"]
    first = consume_demo_request(token)
    assert first is not None
    assert first["requests_used"] == 1
    second = consume_demo_request(token)
    assert second is not None
    assert second["requests_used"] == 2
    third = consume_demo_request(token)
    assert third is None


def test_is_demo_username():
    assert is_demo_username("demo:DS-ABC123")
    assert not is_demo_username("alice")
