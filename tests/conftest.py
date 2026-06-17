"""Shared pytest fixtures for cli-market-core."""

from __future__ import annotations

import pytest

from market_core import ensure_db_initialized


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Fresh SQLite database in a temp directory."""
    db_file = tmp_path / "test_market.db"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path / "market_data"))
    monkeypatch.setattr("market_core.market_core.DB_FILE", db_file)
    monkeypatch.setattr("market_core.market_core.USE_PG", False)
    monkeypatch.setattr("market_core.market_core._pg_fell_back", False)
    monkeypatch.setattr("market_core.market_core._db_initialized", False)
    ensure_db_initialized()
    yield db_file
    monkeypatch.setattr("market_core.market_core._db_initialized", False)