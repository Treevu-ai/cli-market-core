"""Tests for order idempotency and payment status transitions."""

from __future__ import annotations

import pytest

from market_core import db_create_order, ensure_db_initialized
from market_core.market_billing import (
    db_claim_webhook_event,
    db_find_order_by_idempotency_key,
    db_set_order_status,
    db_update_order_status,
)
from market_core.order_status import InvalidOrderTransition, validate_order_transition


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "orders_test.db"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr("market_core.market_core.DB_FILE", db_file)
    monkeypatch.setattr("market_core.market_core.USE_PG", False)
    monkeypatch.setattr("market_core.market_core._pg_fell_back", False)
    monkeypatch.setattr("market_core.market_core._db_initialized", False)
    ensure_db_initialized()
    yield db_file


def test_validate_order_transition_pending_to_paid():
    validate_order_transition("pending", "paid")


def test_validate_order_transition_rejects_paid_to_pending():
    with pytest.raises(InvalidOrderTransition):
        validate_order_transition("paid", "pending")


def test_db_create_order_idempotent_replay(isolated_db):
    items = [{"product_id": "p1", "name": "Arroz", "price": 3.5, "store": "wong", "quantity": 1}]
    first = db_create_order(
        "alice",
        items,
        "yape",
        3.5,
        status="pending",
        idempotency_key="idem-001",
    )
    second = db_create_order(
        "alice",
        items,
        "yape",
        3.5,
        status="pending",
        idempotency_key="idem-001",
    )
    assert first["order_id"] == second["order_id"]
    assert second.get("idempotent_replay") is True
    row = db_find_order_by_idempotency_key("alice", "idem-001")
    assert row is not None
    assert row["order_id"] == first["order_id"]


def test_db_set_order_status_valid_transition(isolated_db):
    order = db_create_order(
        "bob",
        [{"product_id": "p2", "name": "Leche", "price": 4.0, "store": "wong", "quantity": 1}],
        "paypal",
        4.0,
        status="pending",
    )
    assert db_set_order_status(order["order_id"], "paid") is True
    assert db_update_order_status(order["order_id"], "paid") is True


def test_db_claim_webhook_event_dedup(isolated_db):
    assert db_claim_webhook_event("evt-1", "paypal") is True
    assert db_claim_webhook_event("evt-1", "paypal") is False


def test_db_set_order_status_invalid_transition(isolated_db):
    order = db_create_order(
        "carol",
        [{"product_id": "p3", "name": "Aceite", "price": 8.0, "store": "wong", "quantity": 1}],
        "yape",
        8.0,
        status="pending",
    )
    assert db_set_order_status(order["order_id"], "paid") is True
    with pytest.raises(InvalidOrderTransition):
        db_set_order_status(order["order_id"], "pending")
