"""Action closure L1-L2 — retailer deep links and exportable shopping lists."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from .market_core import STORES

EXPORT_TTL_HOURS = 72


def retailer_deeplink(
    store: str,
    *,
    product_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    """Best-effort product/search URL for a retailer (L1)."""
    cfg = STORES.get(store) or {}
    base = (cfg.get("base") or "").rstrip("/")
    if not base:
        return None

    platform = cfg.get("platform", "vtex")
    url = None
    if platform == "vtex" and product_id:
        url = f"{base}/{product_id}/p"
    elif name:
        q = quote(name.strip())
        if platform == "shopify":
            url = f"{base}/search?q={q}"
        else:
            url = f"{base}/search?ft={q}"

    if not url:
        return None

    return {
        "type": "retailer_deeplink",
        "store": store,
        "product_id": product_id,
        "url": url,
        "affiliate": False,
        "expires_at": None,
    }


def create_shopping_list_export(db, payload: dict[str, Any], *, ttl_hours: int = EXPORT_TTL_HOURS) -> dict[str, Any]:
    token = uuid.uuid4().hex[:16]
    expires = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
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
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    first_product_id = None
    first_name = None
    for it in items:
        if it.get("resolved_product_id"):
            first_product_id = it["resolved_product_id"]
            first_name = it.get("resolved_name") or it.get("requested")
            break
    deeplink = retailer_deeplink(store, product_id=first_product_id, name=first_name)
    if deeplink:
        links.append(deeplink)

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
