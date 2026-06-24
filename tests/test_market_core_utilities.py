"""Unit tests for market_core session, API client, cart, and DB helpers."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi import HTTPException

from market_core import get_db
from market_core import market_core as mc


def test_session_roundtrip(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(mc, "DATA_DIR", data_dir)
    monkeypatch.setattr(mc, "SESSION_FILE", data_dir / "session.json")
    monkeypatch.delenv("MARKET_API_TOKEN", raising=False)
    monkeypatch.delenv("CLI_MARKET_API_KEY", raising=False)

    mc.save_session("alice", "tok-abc", refresh_token="ref-1", expires_at="2026-12-31")
    assert mc.get_token() == "tok-abc"
    assert mc.get_session_username() == "alice"
    assert mc.get_refresh_token() == "ref-1"


def test_get_token_prefers_market_api_token_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(mc, "DATA_DIR", data_dir)
    monkeypatch.setattr(mc, "SESSION_FILE", data_dir / "session.json")
    mc.save_session("alice", "tok-from-file")
    monkeypatch.setenv("MARKET_API_TOKEN", "sk-from-env")
    assert mc.get_token() == "sk-from-env"


def test_get_token_reads_api_key_field_and_utf8_bom(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    session = data_dir / "session.json"
    monkeypatch.setattr(mc, "DATA_DIR", data_dir)
    monkeypatch.setattr(mc, "SESSION_FILE", session)
    monkeypatch.delenv("MARKET_API_TOKEN", raising=False)
    monkeypatch.delenv("CLI_MARKET_API_KEY", raising=False)
    session.write_bytes(
        b"\xef\xbb\xbf" + b'{"username":"bob","api_key":"sk-bom-key"}',
    )
    assert mc.get_token() == "sk-bom-key"
    assert mc.get_session_username() == "bob"


def test_format_api_error_validation_list():
    detail = [{"loc": ["body", "email"], "msg": "Field required", "type": "missing"}]
    assert "email" in mc._format_api_error(detail)
    assert "Field required" in mc._format_api_error(detail)


def test_last_search_cache(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(mc, "DATA_DIR", data_dir)
    monkeypatch.setattr(mc, "LAST_SEARCH_FILE", data_dir / "last_search.json")

    results = [{"id": "p1", "name": "Leche", "price": 5.0, "store": "wong_pe", "currency": "PEN"}]
    mc.save_last_search(results)
    loaded = mc.load_last_search()
    assert len(loaded) == 1
    assert loaded[0]["product_id"] == "p1"


def test_api_timeout_search_paths(monkeypatch):
    monkeypatch.delenv("MARKET_API_TIMEOUT", raising=False)
    monkeypatch.delenv("MARKET_SEARCH_TIMEOUT", raising=False)
    assert mc._api_timeout("/products/search", "POST") == 45.0
    assert mc._api_timeout("/health", "GET") == 45.0
    monkeypatch.setenv("MARKET_SEARCH_TIMEOUT", "90")
    assert mc._api_timeout("/products/compare", "POST") == 90.0


def test_api_client_handles_error(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(mc, "DATA_DIR", data_dir)
    monkeypatch.setattr(mc, "SESSION_FILE", data_dir / "session.json")
    monkeypatch.setattr(mc, "API", "http://127.0.0.1:9999")

    class FakeResp:
        status_code = 503
        text = "unavailable"

        def json(self):
            return {"detail": "service down"}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp())
    out = mc.api("GET", "/health")
    assert out["error"] == "service down"
    assert out["status"] == 503


def test_product_from_json_fallback(monkeypatch):
    monkeypatch.setattr(
        mc,
        "resolve_store_config",
        lambda _sid: {"name": "Wong", "currency": "PEN", "platform": "vtex"},
    )
    monkeypatch.setattr(mc, "STORES", {"wong_pe": {"name": "Wong", "currency": "PEN"}})

    def _boom(*_a, **_k):
        raise ImportError("no connector")

    monkeypatch.setattr("market_connectors.get_connector", _boom, raising=False)
    out = mc.product_from_json({"id": "99", "name": "Arroz", "price": 4.5}, "wong_pe")
    assert out["id"] == "99"
    assert out["price"] == 4.5
    assert out["currency"] == "PEN"


def test_cart_lifecycle(isolated_db):
    cart_id = mc.db_add_to_cart("user1", "p1", "Leche", 5.0, "wong_pe", "Wong", 2)
    assert cart_id > 0
    items = mc.db_get_cart("user1")
    assert len(items) == 1
    assert items[0]["quantity"] == 2

    mc.db_update_cart_item("user1", int(items[0]["cart_id"]), 5)
    assert mc.db_get_cart("user1")[0]["quantity"] == 5

    mc.db_remove_cart_item("user1", int(items[0]["cart_id"]))
    assert mc.db_get_cart("user1") == []


def test_save_price_snapshot_upsert(isolated_db, monkeypatch):
    monkeypatch.setattr(
        mc,
        "STORES",
        {"wong_pe": {"currency": "PEN", "line": "supermercados", "name": "Wong"}},
    )
    mc.save_price_snapshot(
        {
            "product_id": "sku-1",
            "name": "Leche 1L",
            "price": 5.5,
            "list_price": 6.0,
            "store": "wong_pe",
            "store_name": "Wong",
        }
    )
    db = get_db()
    try:
        row = db.execute(
            "SELECT price, list_price FROM price_snapshots WHERE product_id = 'sku-1'"
        ).fetchone()
        assert float(row["price"]) == 5.5
    finally:
        db.close()

    mc.save_price_snapshot({"product_id": "sku-1", "name": "Leche 1L", "price": 5.0, "store": "wong_pe"})
    db = get_db()
    try:
        row = db.execute("SELECT price FROM price_snapshots WHERE product_id = 'sku-1'").fetchone()
        assert float(row["price"]) == 5.0
    finally:
        db.close()


def test_check_rate_limit_sqlite(isolated_db):
    for _ in range(3):
        mc.check_rate_limit_sqlite("10.0.0.1", window_secs=60, max_req=10, daily_max=100)
    with pytest.raises(HTTPException) as exc:
        for _ in range(12):
            mc.check_rate_limit_sqlite("10.0.0.2", window_secs=60, max_req=10, daily_max=100)
    assert exc.value.status_code == 429


def test_api_key_create_and_validate(isolated_db):
    created = mc.db_create_api_key("dev", scopes="read", label="test")
    assert created["key"].startswith("sk-")
    validated = mc.db_validate_api_key(created["key"])
    assert validated is not None
    assert validated["username"] == "dev"
    keys = mc.db_list_api_keys("dev")
    assert len(keys) == 1
    assert mc.db_revoke_api_key("dev", keys[0]["id"]) is True
    assert mc.db_validate_api_key(created["key"]) is None


def test_db_auth_brute_force(isolated_db):
    mc.db_record_auth_failure("alice")
    mc.db_record_auth_failure("alice")
    mc.db_check_auth_brute_force("alice", max_attempts=5)
    for _ in range(4):
        mc.db_record_auth_failure("alice")
    with pytest.raises(HTTPException) as exc:
        mc.db_check_auth_brute_force("alice", max_attempts=5)
    assert exc.value.status_code == 429


def test_db_users_and_orders(isolated_db):
    from market_core import db_create_order

    mc.db_save_user("carol", "hash-xyz", token="tok-1")
    users = mc.db_get_users()
    assert users["carol"]["password"] == "hash-xyz"

    order = db_create_order(
        "carol",
        [{"product_id": "p9", "name": "Pan", "price": 2.0, "store": "wong_pe", "quantity": 2}],
        "yape",
        4.0,
        status="pending",
    )
    orders = mc.db_get_orders("carol")
    assert len(orders) == 1
    assert orders[0]["order_id"] == order["order_id"]
    assert len(orders[0]["items"]) == 1


def test_save_search_query(isolated_db):
    mc.save_search_query("leche", "supermercados", "wong_pe", 12)
    db = get_db()
    try:
        row = db.execute("SELECT query, num_results FROM search_queries").fetchone()
        assert row["query"] == "leche"
        assert row["num_results"] == 12
    finally:
        db.close()