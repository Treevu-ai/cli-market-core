"""Shared async retry helper for payment connector HTTP calls."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_BACKOFF = (2.0, 4.0, 8.0)
RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})


class RetryableHTTPError(Exception):
    """Transient HTTP failure that may succeed on retry."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


def is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, RetryableHTTPError):
        return True
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)):
        return True
    return False


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    backoff: tuple[float, ...] = DEFAULT_BACKOFF,
    retryable: Callable[[BaseException], bool] | None = None,
    label: str = "request",
) -> T:
    """Run async callable with exponential backoff on transient failures."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    is_retryable = retryable or is_retryable_exception
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts or not is_retryable(exc):
                raise
            delay = backoff[min(attempt - 1, len(backoff) - 1)]
            logger.warning(
                "%s attempt %d/%d failed (%s); retry in %.1fs",
                label,
                attempt,
                max_attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    raise last_exc  # pragma: no cover


async def request_with_retry(
    method: str,
    url: str,
    *,
    timeout: float = 15.0,
    max_attempts: int = 3,
    backoff: tuple[float, ...] = DEFAULT_BACKOFF,
    label: str = "http",
    **kwargs,
) -> httpx.Response:
    """Issue one HTTP request with retry on transient errors."""

    async def _once() -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code in RETRYABLE_STATUS_CODES:
                raise RetryableHTTPError(resp.status_code, resp.text[:200])
            return resp

    return await with_retry(_once, max_attempts=max_attempts, backoff=backoff, label=label)
