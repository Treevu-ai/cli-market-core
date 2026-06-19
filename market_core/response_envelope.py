"""Unified response envelope for all v1 endpoints.

Every CLI Market endpoint should return ``{"data": …, "meta": …, "trace": …}``.
This module provides the builder, freshness computation, confidence aggregation,
and a timing context manager so the backend can adopt the schema incrementally.

Usage (backward-compatible, opt-in via ``enveloped=True``)::

    from market_core.response_envelope import envelope, with_meta, timing

    with timing() as t:
        result = query_prices(db, country="PE")

    return envelope(
        result["items"],
        freshness_seconds=compute_freshness_seconds(result["items"]),
        confidence=aggregate_confidence(result["items"]),
        latency_ms=t.elapsed_ms,
    )
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any


# ── Public API ──────────────────────────────────────────────────────────────────

def envelope(
    data: Any,
    *,
    freshness_seconds: int | None = None,
    confidence: str = "ok",
    latency_ms: float | None = None,
    request_id: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap *data* in the canonical CLI Market response envelope.

    Args:
        data: The payload (list, dict, or scalar).
        freshness_seconds: Age of the oldest data point in seconds, or ``None``.
        confidence: Aggregate tier — ``"ok"``, ``"warn"``, or ``"low"``.
        latency_ms: Request-processing wall time in milliseconds.
        request_id: Opaque trace id. Auto-generated when omitted.
        extra_meta: Additional metadata fields merged into ``meta``.
    """
    meta: dict[str, Any] = {
        "freshness_seconds": freshness_seconds,
        "confidence": confidence,
        "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
    }
    if extra_meta:
        meta.update(extra_meta)

    return {
        "data": data,
        "meta": meta,
        "trace": {
            "request_id": request_id or uuid.uuid4().hex[:8],
            "version": "1.0",
            "timestamp": _now_iso(),
        },
    }


def with_meta(
    data: Any,
    *,
    freshness_seconds: int | None = None,
    confidence: str = "ok",
    latency_ms: float | None = None,
    request_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Shorthand for :func:`envelope` when no positional-only args are needed."""
    return envelope(
        data,
        freshness_seconds=freshness_seconds,
        confidence=confidence,
        latency_ms=latency_ms,
        request_id=request_id,
        extra_meta=extra if extra else None,
    )


# ── Freshness ───────────────────────────────────────────────────────────────────

def compute_freshness_seconds(
    items: list[dict],
    *,
    timestamp_field: str = "queried_at",
    now: datetime | None = None,
) -> int | None:
    """Seconds since the *oldest* ``timestamp_field`` across *items*.

    For paginated results the envelope reflects the stalest data point.
    Returns ``None`` when no timestamps are available.
    """
    if not items:
        return None
    _now = now or datetime.now(timezone.utc)
    oldest: datetime | None = None
    for item in items:
        ts = item.get(timestamp_field)
        if ts is None:
            continue
        dt = _parse_timestamp(ts)
        if dt is None:
            continue
        if oldest is None or dt < oldest:
            oldest = dt
    if oldest is None:
        return None
    return max(0, int((_now - oldest).total_seconds()))


def freshness_from_string(
    timestamp_str: str | None,
    now: datetime | None = None,
) -> int | None:
    """Compute freshness from a single timestamp string (e.g. ``snapshot_at``)."""
    if not timestamp_str:
        return None
    dt = _parse_timestamp(timestamp_str)
    if dt is None:
        return None
    _now = now or datetime.now(timezone.utc)
    return max(0, int((_now - dt).total_seconds()))


# ── Confidence ──────────────────────────────────────────────────────────────────

# Canonical ordering: worst → best
_CONFIDENCE_RANK: dict[str, int] = {
    "crit": 0,
    "suspect": 0,
    "low": 0,
    "warn": 1,
    "ok": 2,
}


def aggregate_confidence(
    items: list[dict],
    *,
    confidence_field: str = "confidence",
    fallback: str = "ok",
) -> str:
    """Derive envelope-level confidence from item-level flags (worst wins).

    Returns *fallback* when *items* is empty.
    """
    if not items:
        return fallback
    worst_rank = 2
    worst_label = "ok"
    for item in items:
        c = item.get(confidence_field, "ok")
        rank = _CONFIDENCE_RANK.get(str(c), 2)
        if rank < worst_rank:
            worst_label = str(c)
            worst_rank = rank
            if worst_rank == 0:
                break
    return worst_label


# ── Timing ──────────────────────────────────────────────────────────────────────

class _TimingContext:
    elapsed_ms: float = 0.0


@contextmanager
def timing():
    """Context manager that records wall-clock milliseconds.

    Usage::

        with timing() as t:
            result = do_work()
        print(t.elapsed_ms)  # float
    """
    start = time.perf_counter()
    ctx = _TimingContext()
    try:
        yield ctx
    finally:
        ctx.elapsed_ms = (time.perf_counter() - start) * 1000


# ── Internal helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(ts: Any) -> datetime | None:
    """Parse a timestamp from str, datetime, or SQLite naive string into UTC datetime."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    if isinstance(ts, str) and ts:
        try:
            s = ts.replace("Z", "+00:00")
            if " " in s and "T" not in s:
                s = s.replace(" ", "T", 1)
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None
    return None
