"""Food basket query → product matching (filters non-food artifacts in supermercados)."""

from __future__ import annotations

import re
from typing import Any

from .market_spread import (
    CANASTA_ITEMS,
    _CANASTA_EXCLUDE,
    _CANASTA_ITEM_PATTERNS,
    infer_subcategory,
    matches_canasta_item,
)
from .market_units import is_standard_canasta_pack

# Longest keywords first — maps free-text basket queries to staple keys.
_QUERY_STAPLE_KEYWORDS: list[tuple[str, str]] = [
    ("leche en polvo", "leche"),
    ("leche gloria", "leche"),
    ("leche entera", "leche"),
    ("leche", "leche"),
    ("arroz extra", "arroz"),
    ("arroz superior", "arroz"),
    ("arroz", "arroz"),
    ("aceite vegetal", "aceite"),
    ("aceite de oliva", "aceite"),
    ("aceite", "aceite"),
    ("huevos bandeja", "huevos"),
    ("huevos pardos", "huevos"),
    ("huevos", "huevos"),
    ("huevo", "huevos"),
    ("pollo entero", "pollo"),
    ("pollo", "pollo"),
    ("fideos", "pasta"),
    ("fideo", "pasta"),
    ("pasta", "pasta"),
    ("azucar", "azucar"),
    ("azúcar", "azucar"),
    ("cafe", "cafe"),
    ("café", "cafe"),
    ("queso", "queso"),
    ("pan", "pan"),
]

# Extra artifact tokens beyond canasta excludes (kitchen tools, etc.).
_BASKET_EXTRA_EXCLUDE: dict[str, frozenset[str]] = {
    "huevos": frozenset({
        "batidor", "batidora", "espumador", "molde", "organizador", "cocina",
        "recipiente", "escurridor",
    }),
    "aceite": frozenset({"en aceite", "aceite de coco corporal", "aceite de argan"}),
    "pasta": frozenset({"salsa", "primavera", "salteado", "wok", "sarten", "sartén"}),
    "leche": frozenset({"yogurt", "yogur", "batido"}),
}

_PASTA_PATTERN = re.compile(
    r"\b(fideo|fideos|pasta|spaghetti|espagueti|macarron|macarrón|codito|"
    r"caracol|corbata|canuto|tornillo|cintas|lasagna|lasaña)\b",
    re.I,
)

_KITCHEN_TOOL_TOKENS = frozenset({
    "batidor", "batidora", "espumador", "cuchillo", "tabla", "molde", "utensilio",
    "recipiente", "escurridor", "colador", "sarten", "sartén", "olla", "cacerola",
    "licuadora", "procesador", "cafetera", "dispensador",
})

_CONSERVA_TOKENS = frozenset({
    "atun", "atún", "jurel", "bonito", "caballa", "sardina", "anchoveta", "conserva",
    "filete de",
})


def infer_staple_from_query(query: str) -> str | None:
    text = (query or "").lower().strip()
    if not text:
        return None
    for kw, staple in _QUERY_STAPLE_KEYWORDS:
        if kw in text:
            return staple
    return None


def _excludes_for_staple(staple: str) -> frozenset[str]:
    return _CANASTA_EXCLUDE.get(staple, frozenset()) | _BASKET_EXTRA_EXCLUDE.get(staple, frozenset())


def _query_mentions_kitchen_tool(query: str) -> bool:
    text = (query or "").lower()
    return any(tok in text for tok in _KITCHEN_TOOL_TOKENS)


def _has_excluded_token(name: str, staple: str | None) -> bool:
    text = (name or "").lower()
    if staple:
        for ex in _excludes_for_staple(staple):
            if ex in text:
                return True
    return False


def _matches_pasta_staple(name: str) -> bool:
    text = (name or "").lower()
    if not _PASTA_PATTERN.search(text):
        return False
    for ex in _BASKET_EXTRA_EXCLUDE.get("pasta", ()):
        if ex in text:
            return False
    return True


def _token_boundary_match(query: str, name: str) -> bool:
    tokens = [t for t in re.split(r"\s+", (query or "").lower()) if len(t) >= 3]
    if not tokens:
        return False
    text = (name or "").lower()
    hits = sum(1 for tok in tokens if re.search(rf"\b{re.escape(tok)}\b", text))
    return hits >= len(tokens)


def matches_food_basket_query(query: str, row: dict[str, Any]) -> bool:
    """True when a price_snapshot row is a plausible grocery match for the query."""
    name = str(row.get("name") or "")
    line = str(row.get("line") or "supermercados").strip()
    if line and line != "supermercados":
        return False

    staple = infer_staple_from_query(query)
    text = name.lower()

    if staple in CANASTA_ITEMS:
        if not matches_canasta_item(row, staple):
            return False
        return not _has_excluded_token(name, staple)

    if staple == "pasta":
        return _matches_pasta_staple(name)

    if staple:
        pat = _CANASTA_ITEM_PATTERNS.get(staple)
        if pat and not pat.search(text):
            return False
        if _has_excluded_token(name, staple):
            return False
        return True

    if "aceite" in (query or "").lower() and infer_subcategory("supermercados", name) == "conservas":
        return False
    if "aceite" in (query or "").lower():
        for tok in _CONSERVA_TOKENS:
            if tok in text:
                return False

    if not _token_boundary_match(query, name):
        return False
    if _query_mentions_kitchen_tool(query):
        return True
    return not any(tok in text for tok in _KITCHEN_TOOL_TOKENS)


def score_food_basket_match(query: str, row: dict[str, Any]) -> float:
    if not matches_food_basket_query(query, row):
        return -1.0
    name = str(row.get("name") or "")
    score = 0.0
    staple = infer_staple_from_query(query)
    if staple in CANASTA_ITEMS and is_standard_canasta_pack(name, staple):
        score += 3.0
    elif staple == "pasta" and _PASTA_PATTERN.search(name):
        score += 2.0
    tokens = [t for t in re.split(r"\s+", (query or "").lower()) if len(t) >= 3]
    for tok in tokens:
        if re.search(rf"\b{re.escape(tok)}\b", name.lower()):
            score += 1.0
    if staple and infer_subcategory("supermercados", name) == staple:
        score += 1.5
    return score


def pick_best_food_match(query: str, rows: list[Any]) -> dict[str, Any] | None:
    """Return best-scoring row (tie-break: lower price)."""
    ranked: list[tuple[float, float, dict[str, Any]]] = []
    for raw in rows:
        row = dict(raw)
        score = score_food_basket_match(query, row)
        if score < 0:
            continue
        price = float(row.get("price") or 999999)
        ranked.append((score, price, row))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[0][2]


def food_search_hint(query: str) -> str:
    """Disambiguated live-search hint for action links."""
    staple = infer_staple_from_query(query)
    q = (query or "").strip()
    if staple == "huevos":
        return "huevos bandeja"
    if staple == "aceite":
        return "aceite vegetal cocina"
    if staple == "pasta":
        return q if "fideo" in q.lower() else f"fideos {q}".strip()
    return q
