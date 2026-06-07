"""PR3 — build_intel_brief and get_scores."""

from __future__ import annotations

from market_core import ensure_db_initialized, get_db
from market_core.market_indicators import build_intel_brief, get_scores, seed_indicator_definitions


def test_build_intel_brief_shape():
    ensure_db_initialized()
    db = get_db()
    try:
        seed_indicator_definitions(db)
        brief = build_intel_brief(db, country="PE", line="supermercados", days=7)
    finally:
        db.close()

    assert "headline" in brief
    assert "shelf" in brief
    assert "macro_gap" in brief
    assert "confidence" in brief
    assert "scores" in brief
    assert "sources" in brief
    assert brief["country"] == "PE"
    assert brief["line"] == "supermercados"
    assert brief["days"] == 7
    assert "stores_active" in brief["confidence"]


def test_build_intel_brief_include_catalog():
    ensure_db_initialized()
    db = get_db()
    try:
        seed_indicator_definitions(db)
        brief = build_intel_brief(db, include_catalog=True)
    finally:
        db.close()

    assert "catalog" in brief
    assert len(brief["catalog"]) >= 10


def test_get_scores_read_only():
    ensure_db_initialized()
    db = get_db()
    try:
        seed_indicator_definitions(db)
        result = get_scores(db, country="PE")
    finally:
        db.close()

    assert result["country"] == "PE"
    assert "scores" in result
    assert "computed_at" in result