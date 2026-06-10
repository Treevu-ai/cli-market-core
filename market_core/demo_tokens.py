"""Temporary demo sessions — search/compare without account (P1-B)."""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from . import market_core
from .market_core import check_rate_limit_sqlite

logger = market_core.logger

DEMO_TOKEN_PREFIX = "demo-"
DEFAULT_TTL_HOURS = int(os.getenv("DEMO_TOKEN_TTL_HOURS", "24"))
DEFAULT_MAX_REQUESTS = int(os.getenv("DEMO_TOKEN_MAX_REQUESTS", "50"))
SESSION_ISSUE_PER_HOUR = int(os.getenv("DEMO_SESSION_ISSUE_PER_HOUR", "10"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_demo_schema(db) -> None:
    if market_core.USE_PG:
        db.execute("""
            CREATE TABLE IF NOT EXISTS demo_sessions (
                session_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                client_ip TEXT NOT NULL DEFAULT '',
                fingerprint TEXT NOT NULL DEFAULT '',
                requests_used INTEGER NOT NULL DEFAULT 0,
                max_requests INTEGER NOT NULL DEFAULT 50,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    else:
        db.execute("""
            CREATE TABLE IF NOT EXISTS demo_sessions (
                session_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                client_ip TEXT NOT NULL DEFAULT '',
                fingerprint TEXT NOT NULL DEFAULT '',
                requests_used INTEGER NOT NULL DEFAULT 0,
                max_requests INTEGER NOT NULL DEFAULT 50,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_demo_sessions_expires ON demo_sessions(expires_at)")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _parse_expires(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _row_to_dict(row) -> dict:
    d = dict(row)
    exp = _parse_expires(d.get("expires_at"))
    if exp:
        d["expires_at"] = exp.strftime("%Y-%m-%dT%H:%M:%SZ")
    return d


def _session_valid(row: dict | None) -> dict | None:
    if not row:
        return None
    exp = _parse_expires(row.get("expires_at"))
    if not exp or exp <= _now():
        return None
    if int(row.get("requests_used") or 0) >= int(row.get("max_requests") or 0):
        return None
    return row


def issue_demo_token(
    *,
    client_ip: str = "",
    fingerprint: str = "",
    ttl_hours: int | None = None,
    max_requests: int | None = None,
) -> dict:
    """Mint a short-lived demo bearer token (search/compare only)."""
    ttl = ttl_hours if ttl_hours is not None else DEFAULT_TTL_HOURS
    max_req = max_requests if max_requests is not None else DEFAULT_MAX_REQUESTS
    ip = (client_ip or "unknown").strip()[:64]
    fp = (fingerprint or "").strip()[:128]
    rate_key = f"demo-issue:{ip}:{hashlib.sha256(fp.encode()).hexdigest()[:12]}"
    check_rate_limit_sqlite(
        rate_key,
        window_secs=3600,
        max_req=SESSION_ISSUE_PER_HOUR,
        daily_max=SESSION_ISSUE_PER_HOUR * 6,
    )

    token = f"{DEMO_TOKEN_PREFIX}{secrets.token_urlsafe(24)}"
    session_id = f"DS-{uuid.uuid4().hex[:10].upper()}"
    expires = _now() + timedelta(hours=max(1, min(ttl, 72)))
    expires_iso = expires.strftime("%Y-%m-%dT%H:%M:%SZ")

    db = market_core.get_db()
    db.execute(
        """
        INSERT INTO demo_sessions (
            session_id, token_hash, client_ip, fingerprint, max_requests, expires_at, created_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (session_id, _hash_token(token), ip, fp, max_req, expires_iso, _now_iso()),
    )
    db.commit()
    db.close()
    return {
        "demo_token": token,
        "session_id": session_id,
        "expires_at": expires_iso,
        "max_requests": max_req,
        "requests_remaining": max_req,
    }


def validate_demo_token(token: str) -> dict | None:
    if not (token or "").startswith(DEMO_TOKEN_PREFIX):
        return None
    db = market_core.get_db()
    row = db.execute(
        "SELECT * FROM demo_sessions WHERE token_hash=?",
        (_hash_token(token),),
    ).fetchone()
    db.close()
    valid = _session_valid(dict(row) if row else None)
    return _row_to_dict(valid) if valid else None


def consume_demo_request(token: str) -> dict | None:
    """Validate token and increment request counter atomically."""
    if not (token or "").startswith(DEMO_TOKEN_PREFIX):
        return None
    db = market_core.get_db()
    row = db.execute(
        "SELECT * FROM demo_sessions WHERE token_hash=?",
        (_hash_token(token),),
    ).fetchone()
    if not row:
        db.close()
        return None
    data = dict(row)
    if not _session_valid(data):
        db.close()
        return None
    used = int(data.get("requests_used") or 0) + 1
    db.execute(
        "UPDATE demo_sessions SET requests_used=? WHERE session_id=? AND requests_used=?",
        (used, data["session_id"], int(data.get("requests_used") or 0)),
    )
    db.commit()
    updated = db.execute(
        "SELECT * FROM demo_sessions WHERE session_id=?",
        (data["session_id"],),
    ).fetchone()
    db.close()
    if not updated:
        return None
    out = _row_to_dict(dict(updated))
    out["requests_remaining"] = max(0, int(out.get("max_requests") or 0) - int(out.get("requests_used") or 0))
    return out


def is_demo_token(token: str) -> bool:
    return (token or "").startswith(DEMO_TOKEN_PREFIX)


def is_demo_username(username: str) -> bool:
    return (username or "").startswith("demo:")
