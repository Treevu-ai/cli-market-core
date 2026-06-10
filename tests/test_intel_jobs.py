"""Tests for intel_jobs queue (Price Pulse async)."""

from __future__ import annotations

import pytest

from market_core import ensure_db_initialized
from market_core.intel_jobs import (
    db_claim_next_intel_job,
    db_create_intel_job,
    db_get_intel_job,
    db_list_intel_jobs,
    db_update_intel_job,
)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "intel_jobs_test.db"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr("market_core.market_core.DB_FILE", db_file)
    monkeypatch.setattr("market_core.market_core.USE_PG", False)
    monkeypatch.setattr("market_core.market_core._pg_fell_back", False)
    monkeypatch.setattr("market_core.market_core._db_initialized", False)
    ensure_db_initialized()
    yield db_file


def test_db_create_and_get_intel_job(isolated_db):
    job = db_create_intel_job("alice", country="PE", callback_url="https://example.com/hook")
    assert job["job_id"].startswith("PP-")
    assert job["status"] == "queued"
    assert job["country"] == "PE"
    fetched = db_get_intel_job(job["job_id"])
    assert fetched is not None
    assert fetched["username"] == "alice"
    assert fetched["callback_url"] == "https://example.com/hook"


def test_db_claim_next_intel_job_exclusive(isolated_db):
    j1 = db_create_intel_job("bob", country="CO")
    j2 = db_create_intel_job("carol", country="MX")
    claimed = db_claim_next_intel_job()
    assert claimed is not None
    assert claimed["job_id"] == j1["job_id"]
    assert claimed["status"] == "running"
    second = db_claim_next_intel_job()
    assert second is not None
    assert second["job_id"] == j2["job_id"]
    third = db_claim_next_intel_job()
    assert third is None


def test_db_update_intel_job_completion(isolated_db):
    job = db_create_intel_job("dave")
    job_id = job["job_id"]
    assert db_update_intel_job(job_id, status="running", progress=50, progress_label="working") is True
    done = db_get_intel_job(job_id)
    assert done["status"] == "running"
    assert done["progress"] == 50
    assert db_update_intel_job(
        job_id,
        status="completed",
        progress=100,
        output_path="/tmp/report.md",
    ) is True
    final = db_get_intel_job(job_id)
    assert final["status"] == "completed"
    assert final["output_path"] == "/tmp/report.md"
    assert final.get("completed_at")


def test_db_list_intel_jobs_for_user(isolated_db):
    db_create_intel_job("eve", country="PE")
    db_create_intel_job("eve", country="CL")
    db_create_intel_job("frank", country="AR")
    rows = db_list_intel_jobs("eve", limit=10)
    assert len(rows) == 2
    assert all(r["username"] == "eve" for r in rows)
