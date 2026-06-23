# Public Message Alignment Plan — Cost-of-Living OS @ 1.11.0

> **For agentic workers:** Implement task-by-task. Check off `- [ ]` items as you go.  
> **Goal:** Make every public surface describe what CLI Market **actually ships** post Wave 4 (PyPI 1.11.0, 32 MCP default, `market optimize`, affordability, TCO, action links).  
> **Architecture:** Single source of truth (`marketStats` + handoff) → regenerate manifests → update human copy → verify with grep-based gates.  
> **Repos:** `cli-market-world` (primary), `cli-market-core` (package metadata), `procure-copilot` (secondary), GitHub repo descriptions (manual).

---

## North star (what we are now)

**One-liner (ES):** CLI Market — sistema operativo de costo de vida y compra para LatAm. Optimiza tu canasta en una llamada.

**One-liner (EN):** CLI Market — cost-of-living and purchase OS for LatAm. Optimize a basket in one call.

**Compound job (default flow):**
```
market optimize leche arroz --country PE --budget 80
→ POST /v1/missions/optimize-purchase
→ BUY_NOW | MONITOR | WAIT + TCO + action_links + provenance
```

**Honesty constraints (must appear somewhere public):**
- Checkout = orden interna CLI Market + pago LATAM; **no** fulfillment en sitio del retailer.
- L3 affiliate = UTMs en deeplinks (`AFFILIATE_STORES`); L4 handoff = stub.
- TCO delivery = simulación VTEX + defaults PE cuando no hay live API.
- `market_stock` / `market_delivery` / `market_price_history` = perfil **full/legacy**, no default.

---

## Phase 0 — Source of truth (1 PR, world)

### Task 0.1: Lock canonical numbers

**Files:**
- Modify: `cli-market-world/ops/sync_market_stats.py` (if any hardcoded fallbacks)
- Verify: `cli-market-world/landing/lib/marketStats.ts` (generated)
- Verify: `cli-market-core/market_core/market_mcp_registry.py` → `public_tool_count("default")` == 32

- [ ] Run from world repo:
```bash
cd cli-market-world
python3 ops/sync_market_stats.py
```
- [ ] Confirm generated values:
  - `mcpTools: 32`, `mcpToolsLegacy: 57`, `indicatorsCount: 44`
  - `pricesVerifiedLabel: "63,000+"`
  - `packageVersion: "1.11.0"` (bump if still 1.10.0)
- [ ] Commit: `chore(marketing): regenerate marketStats from core 1.11.0`

### Task 0.2: Set canonical MCP entry point

**Files:**
- Modify: `cli-market-world/landing/lib/marketStats.ts` (via sync script source)
- Modify: `cli-market-world/mcp.json` + `cli-market-world/landing/public/mcp.json`
- Modify: `cli-market-world/ops/sync_market_stats.py` — shop bundle flags

- [ ] In shop bundle JSON: set `"canonical": true` on `market_optimize_purchase`
- [ ] Set `"canonical": false` on `market_discover` (or keep discover canonical for coverage-only flows — pick **one**; recommend optimize as P0)
- [ ] Regenerate + commit manifests

**Acceptance:** `grep -n '"canonical": true' mcp.json landing/public/mcp.json` shows optimize first in Shop narrative.

---

## Phase 1 — README + machine-readable agents (1 PR, world)

### Task 1.1: README world — quick start + tool count

**Files:**
- Modify: `cli-market-world/README.md` (ES + EN sections)

- [ ] Replace quick start block with:
```bash
pip install cli-market-world
market init
market login
market optimize leche:2 arroz:1 --country PE --budget 80   # compound job (Wave 4)
market basket "arroz:1 aceite:1" --country PE --tco
market search "leche" --country PE
market intel brief --country PE
```
- [ ] Add subsection **"Cost-of-Living OS"** (5 bullets): affordability, TCO, substitutes, household, action links.
- [ ] Change `27 curated MCP tools` → `32 curated MCP tools (57 registered, legacy profile available)`.
- [ ] Unify price count: `63,000+` everywhere (remove `61,000+` in dashboard section ~L209).
- [ ] Fix Starter row: `1,000` → `5,000` req/day (match `landing/lib/buildPricingTiers.ts`).
- [ ] Add note: `market optimize` requires Starter+ tier (matches MCP `min_tier`).

- [ ] Commit: `docs(readme): Cost-of-Living OS quick start + 32 MCP tools`

### Task 1.2: llms.txt + llms-full.txt

**Files:**
- Modify: `cli-market-world/landing/public/llms.txt`
- Modify: `cli-market-world/landing/public/llms-full.txt`

- [ ] Update Key Numbers:
  - `27` → `32` curated MCP tools
  - `61,000+` → `63,000+` prices
  - Add: `default agent flow: market_optimize_purchase (not search→compare→basket)`
- [ ] In llms-full Shop list: add `market_optimize_purchase`, `market_substitutes`, `market_affordability`, `market_household_*`
- [ ] Fix stale pricing if any ($24/$39 → $9/$49)
- [ ] ICP flow section: lead with optimize-purchase happy path

- [ ] Commit: `docs(llms): align agent discovery with Wave 4`

### Task 1.3: agents.json version bump

**Files:**
- Modify: `cli-market-world/landing/public/agents.json`

- [ ] `version` → world `pyproject.toml` version (1.11.0 when bumped)
- [ ] `price_count` / stats fields → match `MARKET_STATS`
- [ ] Capabilities: remove or qualify `stock_check` / `delivery_estimates` / `realtime` unless exposed in default profile

- [ ] Commit: `chore(agents.json): sync version and capabilities with 1.11.0`

---

## Phase 2 — Landing narrative (1–2 PRs, world)

### Task 2.1: Hero — honest execution + optimize demo

**Files:**
- Modify: `cli-market-world/landing/components/Hero.tsx`

- [ ] Subhead ES/EN: replace *"ejecuten comercio real"* with:
  - ES: *"…comparen precios, optimicen canastas y cierren con checkout interno CLI Market (Yape/PayPal) — sin scraping."*
  - EN: equivalent
- [ ] Terminal demo snippet: show `market optimize leche arroz --country PE` instead of/in addition to `market basket`
- [ ] Optional chip: `32 MCP tools · optimize in one call`

- [ ] Commit: `feat(landing): hero aligns with Cost-of-Living OS + honest checkout`

### Task 2.2: CapabilitiesSection — remove overclaim

**Files:**
- Modify: `cli-market-world/landing/components/CapabilitiesSection.tsx`

- [ ] Agent Tools copy: remove `stock, delivery, price history` from default claim. Replace with:
  - *"32 MCP tools — search, basket, compare, optimize-purchase, affordability. Advanced profile adds stock, delivery, legacy aliases."*
- [ ] Procurement card: clarify boundary:
  - *"Multi-retailer basket + budget constraints via API. Enterprise approvals → Procure Copilot."*
- [ ] Link procurement card to `/procure` (already) + mention `market optimize` in Intelligence card

- [ ] Commit: `fix(landing): capabilities match default MCP profile`

### Task 2.3: New or update SolutionSection / MoatSection

**Files:**
- Modify: `cli-market-world/landing/components/SolutionSection.tsx` (exists)
- Optional: `cli-market-world/landing/components/MoatSection.tsx`

- [ ] Add 3-step story:
  1. **Affordability** — canasta pressure / macro gap
  2. **Optimize** — one call, TCO + substitutes
  3. **Action** — deeplinks + export list (affiliate when configured)
- [ ] Use `WORLD_CHANGES.md` P2 messaging: prefer *"Optimiza tu compra en una llamada"* over *"MCP server"*

- [ ] Commit: `feat(landing): Cost-of-Living OS solution narrative`

### Task 2.4: ToolsPage fixes

**Files:**
- Modify: `cli-market-world/landing/components/ToolsPage.tsx`

- [ ] Fix env var: `TOOL_PROFILE` → `MCP_TOOL_PROFILE` (match `mcp.json`)
- [ ] Highlight `market_optimize_purchase` at top of Shop bundle
- [ ] Note tier: Starter+ for optimize; Free gets affordability read?

- [ ] Commit: `fix(tools): MCP_TOOL_PROFILE + optimize prominence`

### Task 2.5: Pricing page — feature bullets

**Files:**
- Modify: `cli-market-world/landing/components/Pricing.tsx`
- Reference: `cli-market-core/market_core/commerce_capabilities.py`

- [ ] Pro tier: mention `market optimize`, TCO delivery (Starter+), action links
- [ ] Free tier: shelf compare; **no** full delivery TCO if that's tier-gated
- [ ] Do not promise retailer checkout

- [ ] Commit: `docs(pricing): Wave 4 features per tier`

---

## Phase 3 — Core package metadata (1 PR, core)

### Task 3.1: README + pyproject + server.json

**Files:**
- Modify: `cli-market-core/README.md`
- Modify: `cli-market-core/pyproject.toml`
- Modify: `cli-market-core/server.json`

- [ ] README opening: *"Cost-of-Living OS intelligence layer — Waves 1–4"*
- [ ] Module table: add `api_routes`, `market_missions`, `market_household`, `market_tco`, `market_substitutes`, `market_receipts`, `market_ecosystem`, `market_action_links`
- [ ] Fix indicators: 34 → 44
- [ ] Add mount snippet from `HANDOFF.md`
- [ ] pyproject `description` + `keywords`: add `cost-of-living`, `affordability`, `household`, `latam`, `procurement`
- [ ] server.json: version `1.11.0`, description matches world `server.json`, tool count 32 default

- [ ] Commit: `docs(core): README and metadata for 1.11.0 Cost-of-Living OS`

### Task 3.2: Handoff doc gap — /v1/capabilities

**Files:**
- Modify: `cli-market-core/market_core/api_routes.py` OR `ops/HANDOFF-COST-OF-LIVING.md`

**Decision (pick one in implementation):**
- A) Add `GET /v1/capabilities` route wrapping `get_commerce_capabilities()` — then document in OpenAPI
- B) Remove REST claim from handoff; document as Python-only

- [ ] If A: add route + test in `tests/test_api_routes_wave4.py`
- [ ] If B: edit handoff only

- [ ] Commit accordingly

---

## Phase 4 — Procure Copilot (1 PR, procure-copilot)

### Task 4.1: Align Procure narrative with infra reality

**Files:**
- Modify: `procure-copilot` landing copy (e.g. `app/procure/page.tsx` or equivalent)
- Reference: `cli-market-world/landing/components/ProcureCopilotPage.tsx`

- [ ] Step 2 Compare: mention `market optimize` / API compound job as engine
- [ ] Step 3 Approve: qualify as *"workflow interno Procure"* — not shipped in base CLI Market API
- [ ] Step 4 Checkout: same disclaimer as CLI Market README
- [ ] Sync `lib/market-stats.ts` from world `sync_market_stats` output (32 tools, 63k+)

- [ ] Commit: `docs(procure): align copy with CLI Market 1.11.0 infra`

---

## Phase 5 — GitHub + SEO surfaces (manual, 30 min)

### Task 5.1: Repository descriptions

- [ ] **cli-market-world** GitHub About: *"Cost-of-living & purchase OS for AI agents in LatAm. 32 MCP tools. pip install cli-market-world"*
- [ ] **cli-market-core** GitHub About: *"Intelligence layer for CLI Market — affordability, TCO, optimize-purchase mission. PyPI 1.11.0"*
- [ ] **procure-copilot**: *"B2B procurement UI on CLI Market price infra"*

### Task 5.2: Regenerate OG / social

**Files:**
- `cli-market-world/landing/public/og.svg`, `og-preview.svg` — already say 32 MCP; verify 1.11.0 in packageVersion-driven assets after sync

---

## Phase 6 — Verification gates (CI-friendly)

### Task 6.1: Add marketing consistency script

**Files:**
- Create: `cli-market-world/ops/verify_public_copy.py`

```python
"""Fail if stale marketing numbers appear in key public files."""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [
    ROOT / "README.md",
    ROOT / "landing/public/llms.txt",
]
FORBIDDEN = [
    (r"\b27 curated MCP\b", "use 32 curated MCP"),
    (r"\b61,000\+", "use 63,000+"),
    (r"TOOL_PROFILE", "use MCP_TOOL_PROFILE on Tools page only"),
]
errors = []
for f in FILES:
    text = f.read_text(encoding="utf-8")
    for pat, msg in FORBIDDEN:
        if re.search(pat, text):
            errors.append(f"{f}: {msg}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print("OK: public copy gate")
```

- [ ] Wire into `.github/workflows/ci.yml` after docs PRs merge
- [ ] Commit: `ci: public copy consistency gate`

### Task 6.2: Manual smoke checklist

- [ ] `curl -s https://cli-market.dev/llms.txt | grep -E "32|optimize"`
- [ ] Browse `/tools` — optimize visible, 32 tools
- [ ] `pip install cli-market-world` → `market hello` mentions optimize or compound job
- [ ] PyPI descriptions match (trigger world publish if needed)

---

## Execution order (recommended)

| Order | Phase | PRs | Depends on |
|-------|-------|-----|------------|
| 1 | Phase 0 | world #1 | core 1.11.0 on PyPI ✅ |
| 2 | Phase 1 | world #2 | Phase 0 |
| 3 | Phase 2 | world #3–4 | Phase 0 |
| 4 | Phase 3 | core #1 | — |
| 5 | Phase 4 | procure #1 | Phase 1 |
| 6 | Phase 5 | manual | Phases 1–3 |
| 7 | Phase 6 | world #5 | Phases 1–2 |

**Parallelizable:** Phase 3 (core) can run alongside Phase 1–2. Procure (Phase 4) after world copy stabilizes.

---

## Definition of done

- [ ] No public file says **27 MCP tools** or **61,000+** prices
- [ ] README + llms + hero mention **`market optimize`** as default procurement flow
- [ ] **Cost-of-Living OS** appears in README (world) + hero subhead or solution section
- [ ] Capabilities do not claim stock/delivery in **default** profile
- [ ] Checkout limitation stated on hero or capabilities (not only README footer)
- [ ] core README/pyproject describe Waves 1–4 modules
- [ ] `verify_public_copy.py` passes in CI
- [ ] `ops/WORLD_CHANGES.md` P2 messaging applied on landing

---

## Out of scope (explicit)

- PyPI publish world package (separate release)
- L4 partner API marketing (wait for contract)
- Full Procure approval workflow implementation (copy-only alignment here)
- cli-market-content blog posts / LinkedIn (optional follow-up)

---

## Estimated scope

- **~6–8 PRs** across 3 repos
- **~25–35 files** touched (mostly markdown + TSX + generated JSON)
- **No backend behavior changes** except optional `GET /v1/capabilities`
