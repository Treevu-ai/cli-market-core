# Cambios requeridos en cli-market-world

> A raíz de `fix(telemetry): backlog P0-P3` en `cli-market-core` (PR mergeado a main, commit `cab9ecf`)

## Resumen

El perfil `default` de MCP tools pasó de 22 a 24 herramientas (se promovieron `market_ticket` y `market_barcode`). El código de world importa todo de core, así que el CLI, MCP server y tool list se actualizan automáticamente. Solo hay que corregir el copy estático.

---

## 1. Actualizar "22 curated" → "24 curated"

Buscar y reemplazar en los siguientes archivos de world:

| Archivo | Qué buscar | Qué poner |
|---|---|---|
| `setup.py` o `pyproject.toml` | `22 curated MCP tools` | `24 curated MCP tools` |
| `README.md` | `22 curated` / `22 MCP tools` | `24 curated` / `24 MCP tools` |
| Landing page / docs | `22 herramientas MCP` | `24 herramientas MCP` |
| Cualquier `server_json_description()` override | `22` | `24` |

### Nota técnica

`market_stats.MCP_TOOLS` devuelve `len(TOOLS)` = **46** (todas las registradas). Ese número es correcto y no cambia. El número "curadas" (default profile) se obtiene con `public_tool_count("default")` que ahora retorna **24**.

---

## 2. Sin cambios de código

Todo lo demás se hereda automáticamente de core al hacer `pip install --upgrade cli-market-core`:

- `list_tools("default")` → 24 tools
- `ObservatoryMiddleware` → normalización de retailer/país
- `observatory_summary(top_n=N)` → parámetro disponible
- `record_agent_event(session_id=...)` → campo aceptado

---

## 3. Verificación post-deploy

```bash
python -c "from market_core.market_mcp_registry import public_tool_count; assert public_tool_count('default') == 24, 'Expected 24 default tools'"
python -c "from market_core.market_mcp_registry import list_tools; names = {t['name'] for t in list_tools('default')}; assert 'market_ticket' in names; assert 'market_barcode' in names"
```

---

## Changelog entry sugerida

```
- Default MCP profile: 22 → 24 curated tools (market_ticket + market_barcode promoted)
```
