"""Intelligence async jobs — Price Pulse report queue."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from . import market_core

logger = market_core.logger

JOB_STATUSES = frozenset({"queued", "running", "completed", "failed"})
JOB_TYPES = frozenset({"price_pulse"})


def ensure_intel_schema(db) -> None:
    if market_core.USE_PG:
        db.execute("""
            CREATE TABLE IF NOT EXISTS intel_jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL DEFAULT 'price_pulse',
                status TEXT NOT NULL DEFAULT 'queued',
                username TEXT NOT NULL,
                country TEXT NOT NULL DEFAULT 'PE',
                progress INTEGER NOT NULL DEFAULT 0,
                progress_label TEXT NOT NULL DEFAULT '',
                output_path TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                callback_url TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
        """)
    else:
        db.execute("""
            CREATE TABLE IF NOT EXISTS intel_jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL DEFAULT 'price_pulse',
                status TEXT NOT NULL DEFAULT 'queued',
                username TEXT NOT NULL,
                country TEXT NOT NULL DEFAULT 'PE',
                progress INTEGER NOT NULL DEFAULT 0,
                progress_label TEXT NOT NULL DEFAULT '',
                output_path TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                callback_url TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT NOT NULL DEFAULT ''
            )
        """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_intel_jobs_status ON intel_jobs(status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_intel_jobs_user ON intel_jobs(username)")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_dict(row) -> dict:
    d = dict(row)
    meta = d.pop("metadata_json", "{}") or "{}"
    try:
        d["metadata"] = json.loads(meta) if isinstance(meta, str) else (meta or {})
    except json.JSONDecodeError:
        d["metadata"] = {}
    return d


def db_create_intel_job(
    username: str,
    *,
    job_type: str = "price_pulse",
    country: str = "PE",
    callback_url: str = "",
    metadata: dict | None = None,
) -> dict:
    if job_type not in JOB_TYPES:
        raise ValueError(f"Unknown job_type: {job_type}")
    job_id = f"PP-{uuid.uuid4().hex[:10].upper()}"
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    db = market_core.get_db()
    db.execute(
        """
        INSERT INTO intel_jobs (
            job_id, job_type, status, username, country, callback_url, metadata_json, created_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (job_id, job_type, "queued", username, country.upper()[:2], callback_url or "", meta_json, _now_iso()),
    )
    db.commit()
    db.close()
    return db_get_intel_job(job_id) or {"job_id": job_id, "status": "queued"}


def db_get_intel_job(job_id: str) -> dict | None:
    db = market_core.get_db()
    row = db.execute("SELECT * FROM intel_jobs WHERE job_id=?", (job_id,)).fetchone()
    db.close()
    return _row_to_dict(row) if row else None


def db_list_intel_jobs(username: str, *, limit: int = 20) -> list[dict]:
    db = market_core.get_db()
    rows = db.execute(
        "SELECT * FROM intel_jobs WHERE username=? ORDER BY created_at DESC LIMIT ?",
        (username, limit),
    ).fetchall()
    db.close()
    return [_row_to_dict(r) for r in rows]


def db_update_intel_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    progress_label: str | None = None,
    output_path: str | None = None,
    error: str | None = None,
) -> bool:
    if status is not None and status not in JOB_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    fields: list[str] = []
    params: list[Any] = []
    if status is not None:
        fields.append("status=?")
        params.append(status)
        if status in ("completed", "failed"):
            fields.append("completed_at=?")
            params.append(_now_iso())
    if progress is not None:
        fields.append("progress=?")
        params.append(progress)
    if progress_label is not None:
        fields.append("progress_label=?")
        params.append(progress_label)
    if output_path is not None:
        fields.append("output_path=?")
        params.append(output_path)
    if error is not None:
        fields.append("error=?")
        params.append(error)
    if not fields:
        return False
    params.append(job_id)
    db = market_core.get_db()
    cur = db.execute(f"UPDATE intel_jobs SET {', '.join(fields)} WHERE job_id=?", params)
    db.commit()
    affected = cur.rowcount
    db.close()
    return affected > 0


def db_claim_next_intel_job(job_type: str = "price_pulse") -> dict | None:
    """Atomically claim oldest queued job (best-effort for SQLite/PG)."""
    db = market_core.get_db()
    row = db.execute(
        "SELECT job_id FROM intel_jobs WHERE job_type=? AND status='queued' ORDER BY created_at ASC LIMIT 1",
        (job_type,),
    ).fetchone()
    if not row:
        db.close()
        return None
    job_id = row["job_id"]
    db.execute(
        "UPDATE intel_jobs SET status='running', progress=0, progress_label='starting' WHERE job_id=? AND status='queued'",
        (job_id,),
    )
    db.commit()
    claimed = db.execute("SELECT * FROM intel_jobs WHERE job_id=? AND status='running'", (job_id,)).fetchone()
    db.close()
    return _row_to_dict(claimed) if claimed else None
