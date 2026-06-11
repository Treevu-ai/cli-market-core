"""Ticket 3.1 — build_sources_health ok / partial / dead classification."""

from __future__ import annotations

from datetime import datetime, timezone

from market_core.source_health import build_sources_health, store_health_state


class _Row(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


class _FakeDb:
    def __init__(self, health_rows, last_seen_rows=None):
        self._health = health_rows
        self._last_seen = last_seen_rows or []

    def execute(self, sql, params=None):
        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

            def fetchone(self):
                return self._rows[0] if self._rows else None

        sql_l = sql.lower()
        if "from store_health" in sql_l:
            return _Result(self._health)
        if "snapshots_7d" in sql_l:
            return _Result([
                _Row(store=r["store"], snapshots_7d=10, total_snapshots=20)
                for r in self._last_seen
            ])
        if "max(queried_at)" in sql_l:
            return _Result(self._last_seen)
        return _Result([])


def test_build_sources_health_classifies_states(monkeypatch):
    monkeypatch.setattr(
        "market_core.source_health.get_default_stores",
        lambda: frozenset({"wong", "tottus", "dead_store"}),
    )
    monkeypatch.setattr(
        "market_core.source_health.STORES",
        {
            "wong": {"name": "Wong", "country": "PE"},
            "tottus": {"name": "Tottus", "country": "PE"},
            "dead_store": {"name": "Dead", "country": "PE"},
        },
    )

    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    health_rows = [
        _Row(store="wong", total_requests=100, total_successes=95, success_pct=95.0,
             consecutive_failures=0, last_success=now.isoformat(), last_error=None),
        _Row(store="tottus", total_requests=100, total_successes=50, success_pct=50.0,
             consecutive_failures=2, last_success=now.isoformat(), last_error="timeout"),
        _Row(store="dead_store", total_requests=100, total_successes=10, success_pct=10.0,
             consecutive_failures=9, last_success=None, last_error="403"),
    ]
    last_seen = [
        _Row(store="wong", last_seen=now.isoformat()),
        _Row(store="tottus", last_seen=now.isoformat()),
    ]

    payload = build_sources_health(_FakeDb(health_rows, last_seen), catalog_only=True, now=now)
    by_store = {s["store"]: s for s in payload["stores"]}

    assert store_health_state(95) == "ok"
    assert store_health_state(50) == "partial"
    assert store_health_state(10) == "dead"

    assert by_store["wong"]["state"] == "ok"
    assert by_store["tottus"]["state"] == "partial"
    assert by_store["dead_store"]["state"] == "dead"
    assert payload["summary"] == {"ok": 1, "partial": 1, "dead": 1, "total": 3}
