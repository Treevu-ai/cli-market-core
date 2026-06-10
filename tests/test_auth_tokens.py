"""Tests for session refresh tokens."""

from __future__ import annotations

import pytest

from market_core import db_save_user, ensure_db_initialized
from market_core.auth_tokens import (
    issue_session_tokens,
    list_sessions_expiring_within,
    lookup_session_token,
    mark_expiry_reminder_sent,
    revoke_all_tokens,
    rotate_token,
)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "auth_tokens_test.db"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr("market_core.market_core.DB_FILE", db_file)
    monkeypatch.setattr("market_core.market_core.USE_PG", False)
    monkeypatch.setattr("market_core.market_core._pg_fell_back", False)
    monkeypatch.setattr("market_core.market_core._db_initialized", False)
    ensure_db_initialized()
    yield db_file


def test_issue_rotate_and_revoke(isolated_db):
    db_save_user("alice", "salt:deadbeef", None)
    issued = issue_session_tokens("alice")
    assert issued["token"]
    assert issued["refresh_token"]
    lookup = lookup_session_token(issued["token"])
    assert lookup and lookup["username"] == "alice" and not lookup["expired"]

    rotated = rotate_token(issued["refresh_token"])
    assert rotated["token"] != issued["token"]

    assert revoke_all_tokens("alice") is True
    assert lookup_session_token(rotated["token"]) is None


def test_list_sessions_expiring_within(isolated_db):
    from datetime import datetime, timedelta, timezone

    from market_core import get_db

    db_save_user("soon", "salt:abc", None)
    issued = issue_session_tokens("soon")
    soon_exp = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = get_db()
    db.execute("UPDATE app_users SET token_expires_at=? WHERE username=?", (soon_exp, "soon"))
    db.commit()
    db.close()
    expiring = list_sessions_expiring_within(days=7)
    assert any(row["username"] == "soon" for row in expiring)
    mark_expiry_reminder_sent("soon")
    assert not any(row["username"] == "soon" for row in list_sessions_expiring_within(days=7))
    assert issued["token"]
