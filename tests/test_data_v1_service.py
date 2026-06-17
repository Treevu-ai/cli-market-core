"""Tests for intelligence API v1 query helpers."""

from __future__ import annotations

from market_core import get_db
from market_core.data_v1_service import (
    _clamp_limit,
    build_coverage_matrix,
    count_flagged_outliers,
)


def test_clamp_limit_bounds():
    assert _clamp_limit(0) == 50
    assert _clamp_limit(9999) == 500
    assert _clamp_limit(25) == 25


def test_build_coverage_matrix(isolated_db, monkeypatch):
    monkeypatch.setattr(
        "market_core.data_v1_service.STORES",
        {
            "wong_pe": {"country": "PE"},
            "metro_pe": {"country": "PE"},
            "jumbo_cl": {"country": "CL"},
        },
    )
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO price_snapshots (product_id, store, name, price, line)
            VALUES ('a', 'wong_pe', 'Leche', 5.0, 'supermercados'),
                   ('b', 'metro_pe', 'Arroz', 4.0, 'supermercados'),
                   ('c', 'jumbo_cl', 'Pan', 3.0, 'supermercados')
            """
        )
        db.commit()
        matrix = build_coverage_matrix(db)
        assert "PE" in matrix["countries"]
        assert "CL" in matrix["countries"]
        assert len(matrix["cells"]) >= 2
    finally:
        db.close()


def test_count_flagged_outliers(isolated_db):
    db = get_db()
    try:
        rows = [
            ("p1", "s1", "Leche 1L", 5.0, "supermercados"),
            ("p2", "s2", "Leche 1L", 5.2, "supermercados"),
            ("p3", "s3", "Leche 1L", 5.1, "supermercados"),
            ("p4", "s4", "Leche 1L", 5.0, "supermercados"),
            ("p5", "s5", "Leche 1L", 5.3, "supermercados"),
            ("p6", "s6", "Leche 1L", 50.0, "supermercados"),
        ]
        for i, (pid, store, name, price, line) in enumerate(rows):
            db.execute(
                """
                INSERT INTO price_snapshots
                    (product_id, store, name, price, line, currency, store_name)
                VALUES (?, ?, ?, ?, ?, 'PEN', ?)
                """,
                (pid, store, name, price, line, store),
            )
        db.commit()
        n = count_flagged_outliers(db)
        assert n >= 1
    finally:
        db.close()