"""Tests for subscription request payment link updates."""

from market_core import ensure_db_initialized
from market_core.market_billing import (
    db_create_subscription_request,
    db_find_subscription_request,
    db_update_subscription_request_payment_link,
)


def test_db_update_subscription_request_payment_link():
    ensure_db_initialized()
    req = db_create_subscription_request("u1", "u1@test.com", "mercadopago:pending")
    ok = db_update_subscription_request_payment_link(req["id"], "https://mp.test/pay")
    assert ok is True
    row = db_find_subscription_request(request_id=req["id"])
    assert row["payment_link"] == "https://mp.test/pay"