"""Phase 2 composite scores in get_scores."""

from __future__ import annotations

import json

from market_core import ensure_db_initialized, get_db
from market_core.market_indicators import get_scores, seed_indicator_definitions


def _insert_value(db, *, key: str, value: float, country: str = "PE", scope: str = "PE:macro") -> None:
    db.execute(
        """
        INSERT INTO indicator_values
            (indicator_key, scope, country, line, value, metadata_json, recorded_at)
        VALUES (?, ?, ?, '', ?, ?, datetime('now'))
        """,
        (key, scope, country, value, json.dumps({})),
    )


def test_phase2_scores_from_latest_values():
    ensure_db_initialized()
    db = get_db()
    try:
        seed_indicator_definitions(db)
        _insert_value(db, key="commodity_input_pressure", value=4.2, country="", scope="global:macro")
        _insert_value(db, key="real_wage_basket_ratio", value=2.1, country="PE", scope="PE:affordability")
        _insert_value(db, key="gtrends_search_momentum", value=1.25, country="PE", scope="PE:enrichment")
        _insert_value(db, key="bcrp_shelf_gap", value=-6.5, country="PE", scope="PE:macro")
        _insert_value(db, key="commodity_transmission_lag", value=3.8, country="", scope="global:composite")
        _insert_value(db, key="ipp_food_co", value=7.5, country="CO", scope="CO:macro")
        db.commit()

        result = get_scores(db, country="PE")
        scores = result["scores"]
        assert "commodity_pressure" in scores
        assert "wage_affordability" in scores
        assert "search_momentum" in scores
        assert "monetary_shelf_gap" in scores
        assert "commodity_transmission" in scores
        assert scores["commodity_pressure"]["label"] == "normal"
        assert scores["search_momentum"]["label"] == "rising"
        assert scores["monetary_shelf_gap"]["label"] == "divergent"
    finally:
        db.close()
