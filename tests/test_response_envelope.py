"""Tests for response_envelope.py — envelope builder, freshness, confidence, timing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from market_core.response_envelope import (
    _parse_timestamp,
    aggregate_confidence,
    compute_freshness_seconds,
    envelope,
    freshness_from_string,
    timing,
)


def test_envelope_basic():
    result = envelope({"key": "value"}, freshness_seconds=3600, confidence="ok", latency_ms=42.7)
    assert result["data"] == {"key": "value"}
    assert result["meta"]["freshness_seconds"] == 3600
    assert result["meta"]["confidence"] == "ok"
    assert result["meta"]["latency_ms"] == 42.7
    assert "request_id" in result["trace"]
    assert len(result["trace"]["request_id"]) == 8
    assert result["trace"]["version"] == "1.0"
    assert "timestamp" in result["trace"]


def test_envelope_extra_meta():
    result = envelope([], freshness_seconds=None, confidence="warn", extra_meta={"total": 5, "limit": 10})
    assert result["data"] == []
    assert result["meta"]["freshness_seconds"] is None
    assert result["meta"]["confidence"] == "warn"
    assert result["meta"]["total"] == 5
    assert result["meta"]["limit"] == 10


def test_envelope_auto_request_id():
    a = envelope("x")
    b = envelope("y")
    assert a["trace"]["request_id"] != b["trace"]["request_id"]


def test_envelope_custom_request_id():
    result = envelope("x", request_id="abc12345")
    assert result["trace"]["request_id"] == "abc12345"


def test_envelope_latency_rounding():
    result = envelope([], latency_ms=123.456789)
    assert result["meta"]["latency_ms"] == 123.5


def test_envelope_latency_none():
    result = envelope([])
    assert result["meta"]["latency_ms"] is None


# ── compute_freshness_seconds ───────────────────────────────────────────────────

def test_freshness_empty():
    assert compute_freshness_seconds([]) is None


def test_freshness_with_timestamps():
    now = datetime.now(timezone.utc)
    items = [
        {"name": "a", "queried_at": (now - timedelta(hours=1)).isoformat()},
        {"name": "b", "queried_at": (now - timedelta(hours=3)).isoformat()},
    ]
    f = compute_freshness_seconds(items, now=now)
    assert f is not None
    assert abs(f - 10800) < 10


def test_freshness_mixed_timestamps():
    now = datetime.now(timezone.utc)
    items = [
        {"name": "a"},
        {"name": "b", "queried_at": (now - timedelta(minutes=30)).isoformat()},
        {"name": "c", "queried_at": None},
    ]
    f = compute_freshness_seconds(items, now=now)
    assert f is not None
    assert abs(f - 1800) < 10


def test_freshness_no_valid_timestamps():
    items = [{"name": "a"}, {"name": "b", "queried_at": ""}]
    assert compute_freshness_seconds(items) is None


def test_freshness_datetime_objects():
    now = datetime.now(timezone.utc)
    items = [{"queried_at": now - timedelta(seconds=42)}]
    f = compute_freshness_seconds(items, now=now)
    assert f is not None
    assert abs(f - 42) < 5


def test_freshness_custom_field():
    now = datetime.now(timezone.utc)
    items = [{"recorded_at": (now - timedelta(hours=2)).isoformat()}]
    f = compute_freshness_seconds(items, timestamp_field="recorded_at", now=now)
    assert f is not None
    assert abs(f - 7200) < 10


def test_freshness_from_string_none():
    assert freshness_from_string(None) is None
    assert freshness_from_string("") is None


def test_freshness_from_string_valid():
    f = freshness_from_string("2024-01-01T00:00:00+00:00")
    assert isinstance(f, int)
    assert f > 0


def test_freshness_from_string_invalid():
    assert freshness_from_string("not-a-date") is None


def test_confidence_empty():
    assert aggregate_confidence([]) == "ok"


def test_confidence_all_ok():
    items = [{"confidence": "ok"}, {"confidence": "ok"}, {"confidence": "ok"}]
    assert aggregate_confidence(items) == "ok"


def test_confidence_worst_warn():
    items = [{"confidence": "ok"}, {"confidence": "warn"}, {"confidence": "ok"}]
    assert aggregate_confidence(items) == "warn"


def test_confidence_worst_crit():
    items = [{"confidence": "ok"}, {"confidence": "crit"}]
    assert aggregate_confidence(items) == "crit"


def test_confidence_worst_suspect():
    items = [{"confidence": "ok"}, {"confidence": "suspect"}, {"confidence": "warn"}]
    assert aggregate_confidence(items) == "suspect"


def test_confidence_missing_field():
    items = [{"name": "a"}, {"confidence": "warn"}]
    assert aggregate_confidence(items) == "warn"


def test_confidence_custom_field():
    items = [{"status": "crit"}, {"status": "ok"}]
    assert aggregate_confidence(items, confidence_field="status") == "crit"


def test_confidence_unknown_tier():
    items = [{"confidence": "unknown_tier"}, {"confidence": "ok"}]
    assert aggregate_confidence(items) == "ok"


def test_confidence_early_exit_on_crit():
    items = [{"confidence": "crit"}, {"confidence": "ok"}, {"confidence": "ok"}]
    assert aggregate_confidence(items) == "crit"


def test_timing_positive():
    with timing() as t:
        _ = sum(range(100000))
    assert t.elapsed_ms > 0


def test_parse_timestamp_none():
    assert _parse_timestamp(None) is None
    assert _parse_timestamp("") is None


def test_parse_timestamp_iso():
    dt = _parse_timestamp("2024-06-15T12:00:00+00:00")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 6


def test_parse_timestamp_utc_z():
    dt = _parse_timestamp("2024-06-15T12:00:00Z")
    assert dt is not None
    assert dt.year == 2024


def test_parse_timestamp_sqlite_naive():
    dt = _parse_timestamp("2024-06-15 12:00:00")
    assert dt is not None
    assert dt.year == 2024
    assert dt.tzinfo is not None


def test_parse_timestamp_datetime_object():
    now = datetime.now(timezone.utc)
    dt = _parse_timestamp(now)
    assert dt == now


def test_parse_timestamp_naive_datetime():
    naive = datetime(2024, 6, 15, 12, 0, 0)
    dt = _parse_timestamp(naive)
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_timestamp_invalid():
    assert _parse_timestamp("not-a-timestamp") is None
    assert _parse_timestamp(42) is None
