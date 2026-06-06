from __future__ import annotations

import hashlib
import hmac

from market_connectors.mercadopago_payments import validate_webhook_signature


def test_validate_webhook_signature_official_example():
    secret = "test_secret"
    ts = "1704908010"
    data_id = "999999999"
    x_request_id = "req-abc"
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    x_signature = f"ts={ts},v1={v1}"
    assert validate_webhook_signature(
        x_signature=x_signature,
        x_request_id=x_request_id,
        data_id=data_id,
        secret=secret,
    )


def test_validate_skips_when_no_secret():
    assert validate_webhook_signature(
        x_signature="",
        x_request_id="",
        data_id="1",
        secret="",
    )