"""Tests for market_db connection wrapper (SQLite path)."""

from __future__ import annotations

from market_core import get_db
from market_core.market_db import _DB, price_snapshots_has_confidence


def test_db_execute_and_commit(isolated_db):
    db = get_db()
    try:
        db.execute(
            "INSERT INTO app_users (username, password_hash) VALUES (?, ?)",
            ("dbtest", "hash"),
        )
        db.commit()
        row = db.execute("SELECT username FROM app_users WHERE username = ?", ("dbtest",)).fetchone()
        assert row["username"] == "dbtest"
    finally:
        db.close()


def test_price_snapshots_has_confidence(isolated_db):
    db = get_db()
    try:
        assert price_snapshots_has_confidence(db) is True
    finally:
        db.close()


def test_db_class_direct(isolated_db):
    db = _DB()
    try:
        db.execute("SELECT 1 AS n").fetchone()
        db.commit()
    finally:
        db.close()