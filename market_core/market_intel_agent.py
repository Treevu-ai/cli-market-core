"""Conversational intelligence agent over the data moat.

A thin, server-side agent that answers natural-language questions about the
price-intelligence data by running a Claude tool-use loop. The model never sees
raw SQL — it can only call a fixed set of typed tools that wrap the existing
data functions (inflation, indicators, prices, dispersion, staple momentum,
price risk, inflation report, procurement signal).
"""

from __future__ import annotations

import json
import os

import httpx

from .market_indicators import (
    compute_internal_inflation_avg,
    compute_staple_price_momentum,
    get_latest_values,
)
from .data_v1_service import (
    query_dispersion,
    query_prices,
)
from .market_intel_products import compute_inflation_report, compute_price_risk, compute_procurement_signal
from .response_envelope import envelope

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BETA_CACHE = "prompt-caching-2024-07-31"
DEFAULT_MODEL = os.getenv("INTEL_AGENT_MODEL", "claude-haiku-4-5")
PAID_MODEL = os.getenv("INTEL_AGENT_PAID_MODEL", "claude-sonnet-4-5")
MAX_TOOL_ITERATIONS = int(os.getenv("INTEL_AGENT_MAX_ITERS", "8"))
MAX_TOKENS = int(os.getenv("INTEL_AGENT_MAX_TOKENS", "4096"))


def _model_for_tier(tier: str | None) -> str:
    """Select model by subscription tier: free -> Haiku, paid -> Sonnet."""
    return PAID_MODEL if tier == "paid" else DEFAULT_MODEL


class AgentUnavailable(RuntimeError):
    """Raised when the agent cannot run (e.g. no API key configured)."""


SYSTEM_PROMPT_BLOCKS = [
    {
        "type": "text",
        "text": (
            "Sos el analista de datos de CLI Market, una plataforma de inteligencia de "
            "precios de retail en LatAm. Respondes preguntas sobre precios, inflacion de "
            "gondola, indicadores y dispersion usando EXCLUSIVAMENTE las herramientas "
            "disponibles. Nunca inventes numeros: si una herramienta devuelve vacio o "
            "null, decilo claramente. Se conciso y concreto, en espanol. Cuando cites "
            "inflacion, aclara que es inflacion observada online y no reemplaza el IPC "
            "oficial. Si la pregunta no se puede responder con los datos, explica que "
            "falta. Para preguntas sobre riesgo de precios usa get_price_risk. Para "
            "presion inflacionaria usa get_inflation_report. Para decisiones de compra "
            "usa get_procurement_signal."
        ),
        "cache_control": {"type": "ephemeral"},
    }
]

TOOLS = [
    {
        "name": "get_inflation",
        "description": (
            "Inflacion promedio observada (delta %% de precios) por pais y linea "
            "sobre los ultimos N dias, calculada desde price_history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "ISO pais, ej. PE, AR, CL. Opcional."},
                "line": {"type": "string", "description": "Linea, ej. supermercados, farmacias. Opcional."},
                "days": {"type": "integer", "description": "Ventana en dias (default 30)."},
            },
        },
    },
    {
        "name": "get_staple_momentum",
        "description": "Cambio %% promedio de precio de los productos de la canasta basica en los ultimos N dias.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "ISO pais. Opcional."},
                "days": {"type": "integer", "description": "Ventana en dias (default 7)."},
            },
        },
    },
    {
        "name": "get_indicators",
        "description": "Ultimos valores de los indicadores del moat por pais/linea.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "ISO pais. Opcional."},
                "line": {"type": "string", "description": "Linea. Opcional."},
                "limit": {"type": "integer", "description": "Maximo de indicadores (default 20)."},
            },
        },
    },
    {
        "name": "get_prices",
        "description": "Snapshots de precios filtrados por pais, linea, moneda o tienda.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "line": {"type": "string"},
                "currency": {"type": "string"},
                "store": {"type": "string"},
                "limit": {"type": "integer", "description": "Maximo de filas (default 20)."},
            },
        },
    },
    {
        "name": "get_dispersion",
        "description": "Dispersion de precios (spread entre tiendas) por subcategoria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "line": {"type": "string"},
                "currency": {"type": "string"},
                "limit": {"type": "integer", "description": "Maximo de grupos (default 20)."},
            },
        },
        "cache_control": {"type": "ephemeral"},
    },
    {
        "name": "get_price_risk",
        "description": "Price Risk Intelligence: which categories are becoming volatile? Returns risk level and reason.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "line": {"type": "string"},
                "days": {"type": "integer", "description": "Analysis window (default 7)."},
            },
        },
    },
    {
        "name": "get_inflation_report",
        "description": "Inflation Intelligence: where is price pressure increasing? Returns internal inflation and macro gap.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "line": {"type": "string"},
                "days": {"type": "integer", "description": "Analysis window (default 30)."},
            },
        },
    },
    {
        "name": "get_procurement_signal",
        "description": "Procurement Intelligence: when should I buy? Returns buy_now/monitor/wait signal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "line": {"type": "string"},
            },
        },
    },
]


def _dispatch(name: str, args: dict, db) -> dict:
    """Execute a single tool against the live data."""
    if name == "get_inflation":
        val = compute_internal_inflation_avg(db, args.get("country"), args.get("line"), int(args.get("days", 30) or 30))
        days_used = int(args.get("days", 30) or 30)
        return {
            "metric_name": "Retail Price Velocity (RPV)",
            "retail_price_velocity_pct": val,
            "avg_inflation_pct": val,  # backward-compat
            "country": args.get("country"),
            "line": args.get("line"),
            "days": days_used,
            "period_note": (
                f"Rolling {days_used}-day shelf price signal (online retailers). "
                "Not equivalent to official CPI — different basket, channel, and period."
            ),
            "note": "RPV: Retail Price Velocity. No reemplaza IPC oficial (INEI, INDEC, etc.).",
        }
    if name == "get_staple_momentum":
        val = compute_staple_price_momentum(db, args.get("country"), int(args.get("days", 7) or 7))
        return {"staple_momentum_pct": val, "country": args.get("country"), "days": int(args.get("days", 7) or 7)}
    if name == "get_indicators":
        values = get_latest_values(db, country=args.get("country"), line=args.get("line"), limit=int(args.get("limit", 20) or 20))
        return {"count": len(values), "indicators": values}
    if name == "get_prices":
        return query_prices(db, clean=True, country=args.get("country"), line=args.get("line"),
                           currency=args.get("currency"), store=args.get("store"), limit=int(args.get("limit", 20) or 20))
    if name == "get_dispersion":
        return query_dispersion(db, clean=True, line=args.get("line"), currency=args.get("currency"),
                               limit=int(args.get("limit", 20) or 20))
    if name == "get_price_risk":
        return compute_price_risk(db, country=args.get("country"), line=args.get("line"),
                                  days=int(args.get("days", 7) or 7))
    if name == "get_inflation_report":
        return compute_inflation_report(db, country=args.get("country"), line=args.get("line"),
                                        days=int(args.get("days", 30) or 30))
    if name == "get_procurement_signal":
        return compute_procurement_signal(db, country=args.get("country"), line=args.get("line"))
    return {"error": f"unknown tool: {name}"}


def ask_intel(question: str, db, *, model: str | None = None, tier: str | None = None, enveloped: bool = False) -> dict:
    """Run the tool-use loop and return {answer, tools_used, iterations, model}.

    Args:
        question: Natural-language question in Spanish.
        db: Database connection.
        model: Override model (overrides tier selection).
        tier: Subscription tier — ``"paid"`` selects Sonnet, otherwise Haiku.
        enveloped: When True, wrap result in canonical envelope.

    Raises AgentUnavailable when ANTHROPIC_API_KEY is not configured.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise AgentUnavailable("ANTHROPIC_API_KEY not configured")

    model = model or _model_for_tier(tier)
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": ANTHROPIC_BETA_CACHE,
        "content-type": "application/json",
    }
    messages: list[dict] = [{"role": "user", "content": question}]
    tools_used: list[str] = []

    with httpx.Client(timeout=60.0) as client:
        for _ in range(MAX_TOOL_ITERATIONS):
            payload = {
                "model": model,
                "max_tokens": MAX_TOKENS,
                "system": SYSTEM_PROMPT_BLOCKS,
                "tools": TOOLS,
                "messages": messages,
            }
            resp = client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                raise AgentUnavailable(f"LLM error {resp.status_code}: {resp.text[:200]}")
            data = resp.json()

            if data.get("stop_reason") == "tool_use":
                messages.append({"role": "assistant", "content": data["content"]})
                tool_results = []
                for block in data["content"]:
                    if block.get("type") == "tool_use":
                        tools_used.append(block["name"])
                        try:
                            result = _dispatch(block["name"], block.get("input", {}), db)
                        except Exception as e:
                            result = {"error": str(e)}
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            answer = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            result = {"answer": answer.strip(), "tools_used": tools_used, "model": model}
            if not enveloped:
                return result
            return envelope(data=result["answer"], freshness_seconds=None, confidence="ok",
                          extra_meta={"tools_used": tools_used, "model": model, "truncated": False})

    result = {"answer": "No pude resolver la consulta dentro del limite de pasos. Proba reformularla.",
              "tools_used": tools_used, "model": model, "truncated": True}
    if not enveloped:
        return result
    return envelope(data=result["answer"], freshness_seconds=None, confidence="ok",
                  extra_meta={"tools_used": tools_used, "model": model or DEFAULT_MODEL, "truncated": True})
