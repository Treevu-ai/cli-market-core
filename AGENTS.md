# AGENTS.md

## Cursor Cloud specific instructions

`cli-market-core` is a Python (>=3.10, CI uses 3.12) intelligence-layer **library**, not a
standalone server. It ships two runnable surfaces plus a test/lint setup. Dependencies are
installed by the startup update script (`pip install -e ".[dev]"`), so they are already present
in this environment.

### Layout / what runs
- FastAPI **v1 router** in `market_core/api_routes.py` — meant to be *mounted* by a backend
  (`app.include_router(router, prefix="/v1")`). There is no committed `main.py`/app entrypoint.
- **MCP stdio server**: `python3 -m market_core.market_mcp` (JSON-RPC over stdio). Its tool
  handlers call an HTTP API via `api()`; point them somewhere with `MARKET_API_URL`
  (defaults to the production Railway URL).
- Top-level `*.py` files (e.g. `market_db.py`) are thin compatibility shims re-exporting
  `market_core.*`; regenerate with `python3 scripts/gen_shims.py`.

### Non-obvious gotchas
- Use `python3` (no `python` alias) and `python3 -m <tool>` — console scripts install to
  `~/.local/bin`, which is **not on PATH** (pytest, ruff, uvicorn, etc.).
- **DB backend**: if `DATABASE_URL` is empty it falls back to a local SQLite DB under
  `~/.market/market.db` (override dir with `MARKET_DATA_DIR`). Production uses PostgreSQL.
- The **SQLite fallback schema is incomplete** relative to production: it lacks
  `price_snapshots.canonical_product_id`, so the golden-taxonomy code path (e.g.
  `GET /v1/intel/price-risk` → `compute_price_risk` → `canonical_price_buckets`) raises
  `no such column: canonical_product_id` on a fresh SQLite DB. Tests that need it do
  `ALTER TABLE price_snapshots ADD COLUMN canonical_product_id TEXT` first. This is expected,
  not an env problem. Other v1 endpoints work fine on empty SQLite (they return empty/zeroed
  enveloped payloads).
- **Importing the package performs outbound HTTPS** to the production API
  (`cli-market-production.up.railway.app`) for a health/stats probe. Set `MARKET_SKIP_LIVE=1`
  (and `CI=true`) to keep tests offline-deterministic, matching CI.

### Commands
- Smoke import check (mirrors CI): import the modules listed in `.github/workflows/ci.yml`.
- Lint: `python3 -m ruff check .` — note the repo currently has ~15 pre-existing ruff findings
  (mostly `F811`/`F541`/`F841` in `market_core.py`, connectors, and tests). CI does **not** gate
  on ruff (only smoke import + pytest), so don't treat these as regressions.
- Tests: `CI=true MARKET_SKIP_LIVE=1 python3 -m pytest -q -m "not integration"`
  (coverage gate is 55%; `integration` tests hit live APIs and are deselected).
- Run the API locally for manual checks: mount `market_core.api_routes.router` in a tiny
  FastAPI app and serve with `python3 -m uvicorn ... --host 0.0.0.0 --port <PORT>`; call
  `ensure_db_initialized()` on startup. Keep `DATABASE_URL` empty for the SQLite path.
