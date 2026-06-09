"""Observatory telemetry — identity, schema, aggregation."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def obs_db(monkeypatch, tmp_path):
    data_dir = tmp_path / "market_data"
    data_dir.mkdir()
    monkeypatch.setenv("MARKET_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OBSERVATORY_TELEMETRY", "1")
    import market_core.market_core as mc

    mc._db_initialized = False
    mc.USE_PG = False
    mc.DB_FILE = data_dir / "market.db"
    mc.ensure_db_initialized()
    yield mc
    mc._db_initialized = False


def test_classify_route_search():
    from market_core.market_observatory import classify_route

    tool, qtype = classify_route("POST", "/products/search")
    assert tool == "market_search"
    assert qtype == "search"


def test_resolve_agent_identity_priority():
    from market_core.market_observatory import resolve_agent_identity

    out = resolve_agent_identity(x_agent_id="agent-cursor-1")
    assert out["agent_id"] == "agent-cursor-1"
    assert out["identity_source"] == "x_agent_id"

    out2 = resolve_agent_identity(session_id="sess-abc")
    assert out2["identity_source"] == "session"
    assert out2["agent_id"].startswith("session_")


def test_record_and_maa(obs_db):
    from market_core.market_observatory import (
        count_maa,
        ensure_observatory_schema,
        observatory_summary,
        record_agent_event,
    )

    ensure_observatory_schema()
    record_agent_event(
        agent_id="agent-test-1",
        tool_name="market_search",
        success=True,
        identity_source="x_agent_id",
        query_type="search",
        country="PE",
    )
    record_agent_event(
        agent_id="agent-test-1",
        tool_name="market_compare",
        success=True,
        identity_source="x_agent_id",
        query_type="compare",
    )
    assert count_maa(days=30) == 1
    summary = observatory_summary(days=30)
    assert summary["maa"] == 1
    assert summary["calls_success"] == 2
    assert summary["top_tools"][0]["name"] in {"market_search", "market_compare"}


def test_noise_filter_skips_smoke():
    from market_core.market_observatory import is_noise_agent, record_agent_event

    assert is_noise_agent("smoke-test-user")
    result = record_agent_event(
        agent_id="smoke-test-user",
        tool_name="market_search",
        success=True,
    )
    assert result.get("skipped") is True
