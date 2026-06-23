"""Wave 3 — receipts crowd truth, ecosystem radar, procurement bulk."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from market_core import get_db
from market_core.market_billing import feature_allowed
from market_core.market_ecosystem import list_ecosystem_launches
from market_core.market_procurement_bulk import run_procurement_bulk
from market_core.market_receipts import (
    compute_moat_confidence,
    compute_moat_diff,
    get_receipt,
    submit_receipt,
)


def _seed(db):
    ts = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
        ("p1", "wong", "Wong", "Leche Gloria Entera 1L", 4.2, "supermercados", "PEN", ts),
    )
    db.commit()


def test_submit_receipt_with_line_items(isolated_db):
    db = get_db()
    try:
        _seed(db)
        result = submit_receipt(
            db,
            url="https://example.com/receipt.jpg",
            country="PE",
            line_items=[{"name": "Leche Gloria Entera 1L", "qty": 2, "unit_price": 4.8}],
        )
        assert result["status"] == "confirmed"
        assert result["moat_diff"]
        assert result["moat_diff"][0]["flag"] == "receipt_higher"
        loaded = get_receipt(db, result["id"])
        assert loaded is not None
        assert loaded["status"] == "confirmed"
    finally:
        db.close()


def test_submit_receipt_pending_without_ocr(isolated_db):
    db = get_db()
    try:
        result = submit_receipt(db, url="https://example.com/r.jpg", country="PE")
        assert result["status"] == "pending"
        assert result["contribution"]["updates_moat_confidence"] is False
    finally:
        db.close()


def test_submit_receipt_failed_empty_ocr(isolated_db):
    db = get_db()
    try:
        result = submit_receipt(db, url="https://example.com/r.jpg", country="PE", ocr={"store": "Wong"})
        assert result["status"] == "failed"
    finally:
        db.close()


def test_moat_confidence_verified_threshold(isolated_db):
    db = get_db()
    try:
        _seed(db)
        for i in range(5):
            submit_receipt(
                db,
                url=f"https://example.com/{i}.jpg",
                country="PE",
                line_items=[{"name": "Leche Gloria Entera 1L", "unit_price": 4.2}],
            )
        conf = compute_moat_confidence(db, product_id="p1", store="wong")
        assert conf["crowd_confirmations_7d"] >= 5
        assert conf["confidence_tier"] == "verified"
    finally:
        db.close()


def test_ecosystem_launches_curated(isolated_db):
    db = get_db()
    try:
        data = list_ecosystem_launches(db, topic="food", days=7, limit=5)
        assert data["topic"] == "food"
        assert len(data["launches"]) >= 1
        assert "manual_curated" in data["sources"]
        assert data["disclaimer"]
    finally:
        db.close()


def test_procurement_bulk(isolated_db):
    db = get_db()
    try:
        _seed(db)
        result = run_procurement_bulk(
            db,
            country="PE",
            lines=[{"sku_query": "leche gloria", "qty": 10}],
            organization_id="org-1",
        )
        assert result["status"] == "ok"
        assert len(result["lines"]) == 1
        assert result["lines"][0]["best_match"] is not None
    finally:
        db.close()


def test_wave3_billing_gates():
    assert feature_allowed("starter", "receipt_crowd")
    assert feature_allowed("pro", "ecosystem_radar")
    assert not feature_allowed("starter", "procurement_bulk")
    assert feature_allowed("enterprise", "procurement_bulk")
