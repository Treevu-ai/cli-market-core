"""Mercado Pago connector unit tests."""

from __future__ import annotations

import pytest

from market_connectors.mercadopago_payments import (
    access_token,
    is_sandbox,
    parse_external_order_id,
)


def test_parse_external_order_id():
    assert parse_external_order_id("CLI-Market-ORD-ABC12345") == "ORD-ABC12345"
    assert parse_external_order_id("ORD-XYZ99999") == "ORD-XYZ99999"
    assert parse_external_order_id("") is None


def test_access_token_sandbox_precedence(monkeypatch):
    monkeypatch.setenv("MERCADOPAGO_SANDBOX", "true")
    monkeypatch.delenv("MERCADOPAGO_ACCESS_TOKEN_PRODUCTION", raising=False)
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN_SANDBOX", "TEST-123")
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN", "FALLBACK")
    assert is_sandbox()
    assert access_token() == "TEST-123"


def test_access_token_production(monkeypatch):
    monkeypatch.setenv("MERCADOPAGO_SANDBOX", "false")
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN_PRODUCTION", "PROD-456")
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN_SANDBOX", "TEST-123")
    assert not is_sandbox()
    assert access_token() == "PROD-456"