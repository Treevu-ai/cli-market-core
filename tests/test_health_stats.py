"""Tests for shared GET /health/stats builder."""

from __future__ import annotations

from datetime import datetime, timezone

from market_core.health_stats import build_health_stats, compute_linkage_metrics, derive_collector_status


class _Row(dict):
    pass


class _StatsDb:
    def execute(self, sql, params=None):
        sql_l = " ".join(sql.lower().split())

        class _R:
            def __init__(self, row):
                self._row = row

            def fetchone(self):
                return self._row

            def fetchall(self):
                return [self._row] if self._row else []

        if "canonical_product_id" in sql_l and "distinct" in sql_l:
            return _R(_Row(n=2))
        if "canonical_product_id" in sql_l:
            return _R(_Row(n=8))
        if "count(distinct store)" in sql_l:
            return _R(_Row(n=4))
        if "queried_at >=" in sql_l:
            return _R(_Row(n=3))
        if "count(*) as n from price_snapshots where price > 0" in sql_l:
            return _R(_Row(n=10))
        if "max(queried_at)" in sql_l:
            return _R(_Row(t="2026-06-10T10:00:00+00:00"))
        if "collector_runs" in sql_l:
            return _R(_Row(finished_at="2026-06-10T09:00:00+00:00", prices_collected=100))
        if "from store_health" in sql_l:
            return _R(None)
        return _R(_Row(n=0))


def test_derive_collector_status_ok(monkeypatch):
    monkeypatch.setattr(
        "market_core.health_stats._age_hours",
        lambda _ts: 1.0,
    )
    status, age = derive_collector_status(
        finished_at="2026-06-10T11:00:00+00:00",
        prices_collected=50,
        moat_age_h=1.0,
    )
    assert status == "ok"
    assert age == 1.0


def test_compute_linkage_metrics():
    metrics = compute_linkage_metrics(_StatsDb())
    assert metrics["linkage_pct"] == 80.0
    assert metrics["golden_linkage_pct"] == 80.0
    assert metrics["unlinked_snapshots"] == 2


def test_build_health_stats_includes_linkage(monkeypatch):
    import market_core.market_core as mc

    monkeypatch.setattr("market_core.health_stats.build_sources_health", lambda *a, **k: {
        "summary": {"ok": 30, "partial": 2, "dead": 0, "total": 32},
    })
    monkeypatch.setattr("market_core.health_stats.derive_collector_status", lambda **k: ("ok", 1.0))
    monkeypatch.setattr(mc, "USE_PG", False)

    out = build_health_stats(_StatsDb(), registry_size=500)
    assert out["golden_linkage_pct"] == 80.0
    assert out["registry_size"] == 500
    assert out["sources_summary"]["ok"] == 30
    assert out["collector_status"] == "ok"
