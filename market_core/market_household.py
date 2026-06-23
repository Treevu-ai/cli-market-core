"""Household profile — persistent budget and restrictions for agent sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

HOUSEHOLD_VERSION = 1

DEFAULT_HOUSEHOLD: dict[str, Any] = {
    "version": HOUSEHOLD_VERSION,
    "size": 1,
    "country": "PE",
    "currency": "PEN",
    "budget_monthly": None,
    "budget_period_start_day": 1,
    "restrictions": {
        "celiac": False,
        "lactose_free": False,
        "vegetarian": False,
    },
    "default_stores": [],
    "default_line": "supermercados",
    "staple_list": [],
    "cadence_days": {"supermercado": 15},
    "goals": [],
}


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = {**DEFAULT_HOUSEHOLD, **payload}
    out["version"] = HOUSEHOLD_VERSION
    if out.get("budget_monthly") is not None and float(out["budget_monthly"]) < 0:
        raise ValueError("budget_monthly must be >= 0")
    out["size"] = max(1, int(out.get("size") or 1))
    out["budget_period_start_day"] = min(28, max(1, int(out.get("budget_period_start_day") or 1)))
    return out


def get_household(db, username: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT payload_json FROM household_profiles WHERE username = ?",
        (username,),
    ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["payload_json"] or "{}")
    except Exception:
        return None


def put_household(db, username: str, payload: dict[str, Any]) -> dict[str, Any]:
    validated = _validate_payload(payload)
    validated["country"] = str(validated.get("country") or "PE").upper()
    db.execute(
        """
        INSERT INTO household_profiles (username, payload_json, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(username) DO UPDATE SET
            payload_json = excluded.payload_json,
            updated_at = datetime('now')
        """,
        (username, json.dumps(validated, ensure_ascii=False)),
    )
    db.commit()
    return validated


def patch_household(db, username: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_household(db, username) or dict(DEFAULT_HOUSEHOLD)
    merged = {**current, **patch}
    if "restrictions" in patch and isinstance(patch["restrictions"], dict):
        merged["restrictions"] = {**current.get("restrictions", {}), **patch["restrictions"]}
    return put_household(db, username, merged)


def household_summary(db, username: str) -> dict[str, Any]:
    profile = get_household(db, username)
    if not profile:
        return {
            "budget_remaining": None,
            "budget_spent_mtd": None,
            "days_left_in_period": None,
            "projected_overspend_pct": 0.0,
            "suggested_action": "setup_profile",
        }

    budget = profile.get("budget_monthly")
    if budget is None:
        return {
            "budget_remaining": None,
            "budget_spent_mtd": None,
            "days_left_in_period": None,
            "projected_overspend_pct": 0.0,
            "suggested_action": "monitor",
        }

    spent = _estimate_spent_mtd(db, username)
    remaining = round(float(budget) - spent, 2)
    now = datetime.now(timezone.utc)
    start_day = int(profile.get("budget_period_start_day") or 1)
    if now.day >= start_day:
        period_start = now.replace(day=start_day, hour=0, minute=0, second=0, microsecond=0)
    else:
        month = now.month - 1 or 12
        year = now.year if now.month > 1 else now.year - 1
        period_start = now.replace(year=year, month=month, day=start_day, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        next_start = period_start.replace(year=period_start.year + 1, month=1)
    else:
        next_start = period_start.replace(month=period_start.month + 1)
    days_left = max(0, (next_start - now).days)
    overspend = 0.0
    if budget and spent > float(budget):
        overspend = round((spent - float(budget)) / float(budget) * 100, 1)

    action = "monitor"
    if remaining < 0:
        action = "wait"
    elif remaining > float(budget) * 0.2:
        action = "buy_now"

    return {
        "budget_remaining": remaining,
        "budget_spent_mtd": round(spent, 2),
        "days_left_in_period": days_left,
        "projected_overspend_pct": overspend,
        "suggested_action": action,
    }


def _estimate_spent_mtd(db, username: str) -> float:
    try:
        rows = db.execute(
            """
            SELECT COALESCE(SUM(total), 0) AS s FROM app_orders
            WHERE username = ? AND created_at >= datetime('now', 'start of month')
            """,
            (username,),
        ).fetchone()
        if rows and rows["s"] is not None:
            return float(rows["s"])
    except Exception:
        pass
    return 0.0


def substitute_constraints_from_household(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not profile:
        return {}
    restrictions = profile.get("restrictions") or {}
    out: dict[str, Any] = {}
    if restrictions.get("vegetarian"):
        out["max_nova"] = 3
    return out
