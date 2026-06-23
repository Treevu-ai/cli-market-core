"""Cross-store product equivalence helpers for search/compare."""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any

from .golden_taxonomy import resolve_canonical_id

_PACK_RE = re.compile(
    r"\b\d+[\.,]?\d*\s*(ml|l|lt|litro|litros|kg|g|gr|gramos|und|unid|pack|u)\b",
    re.I,
)
_BRAND_STOP = frozenset({"de", "la", "el", "y", "con", "sin", "para", "the", "and"})


def _normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def variant_group_key(name: str, *, brand: str | None = None) -> str:
    """Stable grouping key for product variants (strip pack size, normalize tokens)."""
    base = _normalize_text(name)
    base = _PACK_RE.sub(" ", base)
    base = re.sub(r"\s+", " ", base).strip()
    tokens = [t for t in base.split() if t not in _BRAND_STOP and len(t) > 1]
    core = " ".join(tokens[:6]) or base
    if brand:
        return f"{_normalize_text(brand)}|{core}"
    return core


def _name_score(a: str, b: str) -> float:
    na = _normalize_text(a)
    nb = _normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def evaluate_equivalence(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    db=None,
    threshold: float = 0.82,
) -> dict[str, Any]:
    """Score whether two product rows refer to the same SKU variant.

    Returns ``{equivalent, score, method, variant_group_key}``.
    """
    left_name = str(left.get("name") or "")
    right_name = str(right.get("name") or "")
    left_brand = str(left.get("brand") or "")
    right_brand = str(right.get("brand") or "")

    if db is not None:
        left_id = left.get("product_id")
        right_id = right.get("product_id")
        left_canon = resolve_canonical_id(db, str(left_id or ""), left_name)
        right_canon = resolve_canonical_id(db, str(right_id or ""), right_name)
        if left_canon and right_canon and left_canon == right_canon:
            return {
                "equivalent": True,
                "score": 1.0,
                "method": "canonical_product_id",
                "variant_group_key": variant_group_key(left_name, brand=left_brand or None),
            }

    group_l = variant_group_key(left_name, brand=left_brand or None)
    group_r = variant_group_key(right_name, brand=right_brand or None)
    if group_l and group_l == group_r:
        return {
            "equivalent": True,
            "score": 0.95,
            "method": "variant_group_key",
            "variant_group_key": group_l,
        }

    score = _name_score(left_name, right_name)
    equivalent = score >= threshold
    return {
        "equivalent": equivalent,
        "score": round(score, 3),
        "method": "fuzzy_name",
        "variant_group_key": group_l or group_r,
    }
