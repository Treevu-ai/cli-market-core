"""Outbound CRM — DB helpers for retailer activation tracking.

Tracks which outbound targets have had Day 1 sent and on what date,
so the outbound briefing script can generate the correct follow-up
messages without requiring code edits.
"""

from __future__ import annotations

from . import market_core

logger = market_core.logger


def ensure_outbound_schema(db) -> None:
    if market_core.USE_PG:
        db.execute("""
            CREATE TABLE IF NOT EXISTS outbound_activations (
                target_id   TEXT PRIMARY KEY,
                start_date  TEXT NOT NULL,
                notes       TEXT NOT NULL DEFAULT '',
                activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    else:
        db.execute("""
            CREATE TABLE IF NOT EXISTS outbound_activations (
                target_id    TEXT PRIMARY KEY,
                start_date   TEXT NOT NULL,
                notes        TEXT NOT NULL DEFAULT '',
                activated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def db_activate_outbound_target(target_id: str, start_date: str, notes: str = "") -> None:
    db = market_core.get_db()
    if market_core.USE_PG:
        db.execute(
            "INSERT INTO outbound_activations (target_id, start_date, notes) VALUES (%s, %s, %s) "
            "ON CONFLICT(target_id) DO UPDATE SET start_date=EXCLUDED.start_date, "
            "notes=EXCLUDED.notes, activated_at=NOW()",
            (target_id, start_date, notes),
        )
    else:
        db.execute(
            "INSERT INTO outbound_activations (target_id, start_date, notes) VALUES (?,?,?) "
            "ON CONFLICT(target_id) DO UPDATE SET start_date=excluded.start_date, "
            "notes=excluded.notes, activated_at=datetime('now')",
            (target_id, start_date, notes),
        )
    db.commit()
    db.close()
    logger.info("outbound_activate target=%s start=%s", target_id, start_date)


def db_deactivate_outbound_target(target_id: str) -> None:
    db = market_core.get_db()
    if market_core.USE_PG:
        db.execute("DELETE FROM outbound_activations WHERE target_id=%s", (target_id,))
    else:
        db.execute("DELETE FROM outbound_activations WHERE target_id=?", (target_id,))
    db.commit()
    db.close()
    logger.info("outbound_deactivate target=%s", target_id)


def db_get_outbound_activations() -> dict[str, str]:
    """Return {target_id: start_date_str} for all activated targets."""
    db = market_core.get_db()
    rows = db.execute("SELECT target_id, start_date FROM outbound_activations").fetchall()
    db.close()
    return {row[0]: row[1] for row in rows}
