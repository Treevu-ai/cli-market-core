"""Action closure L1-L4 — retailer deep links, exports, affiliate UTMs, partner handoff."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from .market_core import STORES
from .market_feature_flags import affiliate_enabled, external_cart_handoff_enabled

EXPORT_TTL_HOURS = 72


def _affiliate_enabled_for_store(store: str) -> bool:
    cfg = STORES.get(store) or {}
    if cfg.get("affiliate"):
        return True
    raw = (os.getenv("AFFILIATE_STORES") or "").strip()
    if raw:
        allowed = {s.strip() for s in raw.split(",") if s.strip()}
        return store in allowed
    return affiliate_enabled()


def _normalize_store_key(store: str) -> str:
    return (store or "").strip().lower().replace(" ", "")


def _item_store_key(item: dict[str, Any]) -> str:
    raw = item.get("store") or item.get("store_key") or ""
    return _normalize_store_key(str(raw))


def _pick_deeplink_target(
    items: list[dict[str, Any]],
    store: str,
) -> tuple[str | None, str | None, str | None]:
    """Pick product_id, display name, and optional canonical URL for a store deeplink."""
    target = _normalize_store_key(store)
    cfg = STORES.get(store) or {}
    base = (cfg.get("link_base") or cfg.get("base") or "").rstrip("/")

    for it in items:
        if _item_store_key(it) != target:
            continue
        explicit_url = it.get("url")
        if explicit_url and (not base or str(explicit_url).startswith(base)):
            pid = it.get("resolved_product_id") or it.get("product_id")
            name = it.get("resolved_name") or it.get("name") or it.get("requested")
            return (str(pid) if pid else None), (str(name) if name else None), str(explicit_url)

    for it in items:
        pid = it.get("resolved_product_id") or it.get("product_id")
        if _item_store_key(it) == target and pid:
            name = it.get("resolved_name") or it.get("name") or it.get("requested")
            return str(pid), (str(name) if name else None), None

    for it in items:
        if _item_store_key(it) != target:
            continue
        name = it.get("resolved_name") or it.get("name") or it.get("requested")
        if name:
            return None, str(name), None

    for it in items:
        name = it.get("requested") or it.get("name") or it.get("resolved_name")
        if name:
            return None, str(name), None

    return None, None, None


def _append_affiliate_utm(url: str, *, store: str) -> str:
    """Append UTM params for L3 affiliate tracking."""
    source = (os.getenv("AFFILIATE_UTM_SOURCE") or "climarket").strip()
    medium = (os.getenv("AFFILIATE_UTM_MEDIUM") or "agent").strip()
    campaign = (os.getenv("AFFILIATE_UTM_CAMPAIGN") or f"store_{store}").strip()
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("utm_source", source)
    query.setdefault("utm_medium", medium)
    query.setdefault("utm_campaign", campaign)
    return urlunparse(parsed._replace(query=urlencode(query)))


def retailer_deeplink(
    store: str,
    *,
    product_id: str | None = None,
    name: str | None = None,
    url: str | None = None,
    affiliate: bool | None = None,
) -> dict[str, Any] | None:
    """Best-effort product/search URL for a retailer (L1/L3)."""
    cfg = STORES.get(store) or {}
    base = (cfg.get("link_base") or cfg.get("base") or "").rstrip("/")
    if not base:
        return None

    platform = cfg.get("platform", "vtex")
    link_mode = "product"
    resolved_url = None
    if url and str(url).startswith(base):
        resolved_url = str(url)
        link_mode = "canonical"
    elif platform == "vtex" and product_id:
        resolved_url = f"{base}/{product_id}/p"
    elif name:
        q = quote(name.strip())
        if platform == "shopify":
            resolved_url = f"{base}/search?q={q}"
        else:
            resolved_url = f"{base}/search?ft={q}"
        link_mode = "search"

    if not resolved_url:
        return None

    use_affiliate = _affiliate_enabled_for_store(store) if affiliate is None else bool(affiliate)
    if use_affiliate:
        resolved_url = _append_affiliate_utm(resolved_url, store=store)

    return {
        "type": "retailer_deeplink",
        "store": store,
        "product_id": product_id,
        "url": resolved_url,
        "link_mode": link_mode,
        "affiliate": use_affiliate,
        "expires_at": None,
    }


def external_cart_handoff(
    store: str,
    *,
    items: list[dict[str, Any]],
    country: str,
) -> dict[str, Any] | None:
    """L4 partner cart handoff stub — config-driven, no live partner API."""
    if not external_cart_handoff_enabled():
        return None
    partner = (os.getenv("CART_HANDOFF_PARTNER") or "rappi").strip().lower()
    return {
        "type": "external_cart_handoff",
        "partner": partner,
        "store": store,
        "country": country.upper(),
        "status": "stub",
        "url": None,
        "item_count": len(items),
        "message": "Partner API not configured; enable when contract is active.",
    }


def create_shopping_list_export(db, payload: dict[str, Any], *, ttl_hours: int = EXPORT_TTL_HOURS) -> dict[str, Any]:
    token = uuid.uuid4().hex[:16]
    expires = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
    payload = dict(payload)
    payload.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    db.execute(
        """
        INSERT INTO shopping_list_exports (token, payload_json, expires_at, created_at)
        VALUES (?, ?, ?, datetime('now'))
        """,
        (token, json.dumps(payload, ensure_ascii=False), expires),
    )
    db.commit()
    return {
        "type": "export_list",
        "token": token,
        "expires_at": expires,
        "format": payload.get("format", "json"),
    }


def get_shopping_list_export(db, token: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT payload_json, expires_at FROM shopping_list_exports WHERE token = ?",
        (token,),
    ).fetchone()
    if not row:
        return None
    raw_exp = str(row["expires_at"])
    try:
        exp = datetime.fromisoformat(raw_exp.replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            return None
    except Exception:
        pass
    try:
        return json.loads(row["payload_json"] or "{}")
    except Exception:
        return None


def build_action_links(
    db,
    *,
    store: str,
    items: list[dict[str, Any]],
    country: str,
    totals: dict[str, Any],
    include_export: bool = True,
    include_handoff: bool = True,
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    product_id, name, explicit_url = _pick_deeplink_target(items, store)
    deeplink = retailer_deeplink(
        store,
        product_id=product_id,
        name=name,
        url=explicit_url,
    )
    if deeplink:
        links.append(deeplink)

    if include_handoff:
        handoff = external_cart_handoff(store, items=items, country=country)
        if handoff:
            links.append(handoff)

    if include_export:
        export_payload = {
            "title": "Lista optimizada CLI MARKET",
            "country": country.upper(),
            "store": store,
            "currency": totals.get("currency", "PEN"),
            "items": items,
            "totals": totals,
            "format": "json",
            "disclaimer": "Precios observados online; verificar en tienda.",
        }
        export_meta = create_shopping_list_export(db, export_payload)
        links.append(
            {
                **export_meta,
                "url": f"/v1/export/shopping-list/{export_meta['token']}",
            }
        )
    return links
