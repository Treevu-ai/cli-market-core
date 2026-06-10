"""Session access + refresh tokens for enterprise rotation (P1-D)."""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from . import market_core

ACCESS_TTL_DAYS = int(os.getenv("ACCESS_TOKEN_TTL_DAYS", "90"))
REFRESH_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "365"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        s = str(value).replace("Z", "+00:00")
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def ensure_auth_token_schema(db) -> None:
    for col, typ in (
        ("token_expires_at", "TEXT"),
        ("refresh_token_hash", "TEXT"),
        ("token_expiry_reminder_at", "TEXT"),
    ):
        try:
            if market_core.USE_PG:
                db.execute(f"ALTER TABLE app_users ADD COLUMN IF NOT EXISTS {col} {typ}")
            else:
                db.execute(f"ALTER TABLE app_users ADD COLUMN {col} {typ}")
        except Exception:
            pass


def issue_session_tokens(username: str) -> dict:
    """Rotate access + refresh tokens for a user."""
    access = str(uuid.uuid4())
    refresh = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(days=max(1, ACCESS_TTL_DAYS))
    db = market_core.get_db()
    db.execute(
        """
        UPDATE app_users
        SET token=?, token_expires_at=?, refresh_token_hash=?,
            token_expiry_reminder_at=NULL, updated_at=datetime('now')
        WHERE username=?
        """,
        (access, _iso(expires_at), _hash_refresh(refresh), username),
    )
    db.commit()
    db.close()
    return {
        "token": access,
        "refresh_token": refresh,
        "expires_at": _iso(expires_at),
        "refresh_expires_days": REFRESH_TTL_DAYS,
    }


def lookup_session_token(token: str) -> dict | None:
    """Resolve bearer session token; None if unknown."""
    if not token or token.startswith(("sk-", "demo-")):
        return None
    db = market_core.get_db()
    row = db.execute(
        "SELECT username, token_expires_at FROM app_users WHERE token=?",
        (token,),
    ).fetchone()
    db.close()
    if not row:
        return None
    exp = _parse_iso(row["token_expires_at"])
    expired = bool(exp and exp <= _now())
    return {"username": row["username"], "expired": expired}


def rotate_token(refresh_token: str) -> dict:
    """Exchange refresh token for new access (+ rotated refresh)."""
    if not refresh_token:
        raise ValueError("refresh_token required")
    db = market_core.get_db()
    row = db.execute(
        "SELECT username, updated_at FROM app_users WHERE refresh_token_hash=?",
        (_hash_refresh(refresh_token),),
    ).fetchone()
    db.close()
    if not row:
        raise ValueError("invalid refresh token")
    updated = _parse_iso(row["updated_at"])
    if updated and updated + timedelta(days=REFRESH_TTL_DAYS) < _now():
        revoke_all_tokens(row["username"])
        raise ValueError("refresh token expired")
    return issue_session_tokens(row["username"])


def revoke_all_tokens(username: str) -> bool:
    db = market_core.get_db()
    cur = db.execute(
        """
        UPDATE app_users
        SET token=NULL, token_expires_at=NULL, refresh_token_hash=NULL,
            token_expiry_reminder_at=NULL, updated_at=datetime('now')
        WHERE username=?
        """,
        (username,),
    )
    db.commit()
    affected = cur.rowcount
    db.close()
    return affected > 0


def list_sessions_expiring_within(days: int = 7) -> list[dict]:
    """Users with access tokens expiring within `days` and no reminder sent yet."""
    days = max(1, min(days, 30))
    now = _now()
    horizon = now + timedelta(days=days)
    db = market_core.get_db()
    ensure_auth_token_schema(db)
    rows = db.execute(
        """
        SELECT username, token_expires_at, token_expiry_reminder_at
        FROM app_users
        WHERE token IS NOT NULL AND token_expires_at IS NOT NULL
        """
    ).fetchall()
    db.close()
    out: list[dict] = []
    for row in rows:
        if row["token_expiry_reminder_at"]:
            continue
        exp = _parse_iso(row["token_expires_at"])
        if not exp or exp <= now or exp > horizon:
            continue
        out.append(
            {
                "username": row["username"],
                "expires_at": _iso(exp),
                "days_remaining": max(0, int((exp - now).total_seconds() // 86400)),
            }
        )
    return sorted(out, key=lambda x: x["expires_at"])


def mark_expiry_reminder_sent(username: str) -> None:
    db = market_core.get_db()
    db.execute(
        """
        UPDATE app_users
        SET token_expiry_reminder_at=?, updated_at=datetime('now')
        WHERE username=?
        """,
        (_iso(_now()), username),
    )
    db.commit()
    db.close()
