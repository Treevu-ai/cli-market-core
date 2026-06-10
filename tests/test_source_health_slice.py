"""Tests for health_for_stores helper."""

from __future__ import annotations

from market_core.source_health import health_for_stores, store_health_state


def test_store_health_state_thresholds():
    assert store_health_state(85) == "ok"
    assert store_health_state(50) == "partial"
    assert store_health_state(10) == "dead"


def test_health_for_stores_empty():
    class _Db:
        def execute(self, *a, **k):
            class _R:
                def fetchall(self):
                    return []

            return _R()

    out = health_for_stores(_Db(), [])
    assert out["summary"]["total"] == 0
    assert out["stores"] == []
