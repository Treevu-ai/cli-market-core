"""Minimal FastAPI app for local v1 route smoke tests.

Usage::

    CI=true MARKET_SKIP_LIVE=1 python3 -m uvicorn market_core.dev_app:app --host 0.0.0.0 --port 8765
"""

from __future__ import annotations

from fastapi import FastAPI

from .api_routes import router as v1_router
from .market_core import ensure_db_initialized

app = FastAPI(title="CLI Market Core Dev", version="1.10")


@app.on_event("startup")
def _startup() -> None:
    ensure_db_initialized()


app.include_router(v1_router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
