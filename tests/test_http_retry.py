"""Tests for payment connector HTTP retry helper."""

from __future__ import annotations

import httpx
import pytest

from market_connectors.http_retry import (
    RetryableHTTPError,
    is_retryable_exception,
    request_with_retry,
    with_retry,
)


@pytest.mark.asyncio
async def test_with_retry_succeeds_on_third_attempt(monkeypatch):
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RetryableHTTPError(503, "upstream")
        return "ok"

    sleeps: list[float] = []

    async def fake_sleep(sec: float) -> None:
        sleeps.append(sec)

    monkeypatch.setattr("market_connectors.http_retry.asyncio.sleep", fake_sleep)
    result = await with_retry(flaky, backoff=(0.01, 0.02, 0.03), label="test")
    assert result == "ok"
    assert calls["n"] == 3
    assert sleeps == [0.01, 0.02]


@pytest.mark.asyncio
async def test_with_retry_raises_after_max_attempts(monkeypatch):
    async def always_fail():
        raise httpx.TimeoutException("timeout")

    async def noop_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr("market_connectors.http_retry.asyncio.sleep", noop_sleep)
    with pytest.raises(httpx.TimeoutException):
        await with_retry(always_fail, max_attempts=2, backoff=(0.0,), label="test")


@pytest.mark.asyncio
async def test_with_retry_does_not_retry_non_retryable():
    async def boom():
        raise ValueError("bad request")

    with pytest.raises(ValueError):
        await with_retry(boom, max_attempts=3, label="test")


def test_is_retryable_exception():
    assert is_retryable_exception(RetryableHTTPError(429))
    assert is_retryable_exception(httpx.ConnectError("x"))
    assert not is_retryable_exception(ValueError("x"))


@pytest.mark.asyncio
async def test_request_with_retry_retries_502(monkeypatch):
    calls = {"n": 0}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, method, url, **kwargs):
            calls["n"] += 1
            req = httpx.Request(method, url)
            if calls["n"] < 2:
                return httpx.Response(502, request=req)
            return httpx.Response(200, request=req, json={"ok": True})

    async def noop_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr("market_connectors.http_retry.httpx.AsyncClient", lambda **kw: FakeClient())
    monkeypatch.setattr("market_connectors.http_retry.asyncio.sleep", noop_sleep)

    resp = await request_with_retry("GET", "https://example.test/ping", label="test")
    assert resp.status_code == 200
    assert calls["n"] == 2
