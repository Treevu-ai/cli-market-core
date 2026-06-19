# Cambios requeridos en cli-market-backend

> A raíz de `fix(telemetry): backlog P0-P3` en `cli-market-core` (PR mergeado a main, commit `cab9ecf`)

## Resumen

Tres cambios necesarios en backend: (1) propagar `?limit=N` al endpoint de observatory, (2) migrar la BD para agregar `session_id`, (3) actualizar referencias estáticas a "22 tools". El middleware se actualiza solo.

---

## 1. [P1] Endpoint `/analytics/observatory` — parámetro `?limit=N`

**Archivo:** donde se define `GET /analytics/observatory` (probablemente `routers/analytics.py` o similar)

**Antes:**
```python
@router.get("/analytics/observatory")
def observatory(days: int = 30):
    return observatory_summary(days=days)
```

**Después:**
```python
@router.get("/analytics/observatory")
def observatory(days: int = 30, limit: int = 5):
    return observatory_summary(days=days, top_n=limit)
```

La función `observatory_summary()` en core ya acepta `top_n` (default 5, máximo 50). Si no se pasa, el endpoint se comporta exactamente igual que antes (top 5). Backward-compatible.

---

## 2. [P2] Migración de base de datos — columna `session_id`

La tabla `agent_events` necesita una nueva columna. `ensure_observatory_schema()` usa `CREATE TABLE IF NOT EXISTS`, así que **no altera tablas existentes**.

### Opción A — ALTER TABLE (recomendado para producción)

```sql
-- PostgreSQL
ALTER TABLE agent_events ADD COLUMN IF NOT EXISTS session_id TEXT;

-- SQLite
ALTER TABLE agent_events ADD COLUMN session_id TEXT;
```

Ejecutar como parte del script de deploy o migración.

### Opción B — Recrear tabla (solo staging/dev)

Si la tabla es pequeña o estás en staging:
```python
from market_core.market_observatory import ensure_observatory_schema
# Dropea y recrea (pierdes datos de telemetría)
# O simplemente corre ensure_observatory_schema() en una BD limpia
```

### Verificación

```sql
-- PostgreSQL
SELECT column_name FROM information_schema.columns
WHERE table_name = 'agent_events' AND column_name = 'session_id';

-- SQLite
PRAGMA table_info(agent_events);
-- Debe mostrar session_id TEXT en la lista
```

---

## 3. [P3] Actualizar referencias a "22 tools"

Si el backend tiene su propio copy, dashboard, o documentación que menciona "22 curated tools" o "22 herramientas MCP":

| Lugar | Cambio |
|---|---|
| Dashboard HTML | `22` → `24` |
| Respuesta de `/` o `/health` | Si hardcodea el número, actualizar |
| Documentación interna | Buscar `22` y verificar contexto |

El valor canónico se puede obtener en runtime:
```python
from market_core.market_mcp_registry import public_tool_count
curated = public_tool_count("default")  # 24
```

---

## 4. Sin cambios — se actualizan automáticamente

| Componente | Por qué |
|---|---|
| `ObservatoryMiddleware` | Importado de core. Normalización retailer/país y `session_id` se aplican sin cambios en backend. |
| `record_agent_event()` | Acepta `session_id=None` por default. Llamadas existentes no se rompen. |
| `list_tools("default")` | Devuelve 24 tools automáticamente. |
| `MCP_TOOLS` / `market_stats` | Sigue devolviendo 46 (total registradas). Sin cambios. |

---

## 5. Verificación post-deploy

```bash
# 1. Endpoint acepta limit
curl -s "https://cli-market-production.up.railway.app/analytics/observatory?days=30&limit=20" | python -c "import json,sys; d=json.load(sys.stdin); print(f'tools: {len(d[\"top_tools\"])}, retailers: {len(d[\"top_retailers\"])}')"

# 2. Session_id se persiste (requiere auth o endpoint interno)
# Revisar que agent_events tenga la columna

# 3. Tool count en default
python -c "from market_core.market_mcp_registry import public_tool_count; assert public_tool_count('default') == 24"
```

---

## Changelog entry sugerida

```
- /analytics/observatory: acepta ?limit=N (max 50) para top tools/retailers/countries
- agent_events: columna session_id agregada para tracking de funnel
- Default MCP tools: 22 → 24 (market_ticket + market_barcode visibles sin full profile)
```
