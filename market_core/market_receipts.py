"""Receipt crowd truth — compare OCR line items against the data moat."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

RECEIPT_ID_PREFIX = "RCP"
CROWD_WINDOW_DAYS = 7
VERIFIED_CONFIRMATIONS = 5


def _new_receipt_id() -> str:
    return f"{RECEIPT_ID_PREFIX}-{uuid.uuid4().hex[:8].upper()}"


def _match_moat_price(db, name: str, *, store: str | None = None, country: str | None = None) -> dict[str, Any] | None:
    query = f"%{name.strip()}%"
    params: list[Any] = [query]
    sql = """
        SELECT product_id, store, store_name, name, price, currency
        FROM price_snapshots
        WHERE price > 0 AND price < 999999 AND LOWER(name) LIKE LOWER(?)
    """
    if store:
        sql += " AND store = ?"
        params.append(store)
    sql += " ORDER BY price ASC LIMIT 1"
    row = db.execute(sql, params).fetchone()
    if not row:
        return None
    if country:
        from .market_core import STORES

        store_country = (STORES.get(row["store"]) or {}).get("country", "")
        if store_country and str(store_country).upper() != country.upper():
            return None
    return dict(row)


def compute_moat_diff(
    db,
    line_items: list[dict[str, Any]],
    *,
    country: str | None = None,
    store: str | None = None,
) -> list[dict[str, Any]]:
    """Compare receipt line prices to moat snapshots."""
    diffs: list[dict[str, Any]] = []
    for item in line_items:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        receipt_price = float(item.get("unit_price") or item.get("price") or 0)
        if receipt_price <= 0:
            continue
        match = _match_moat_price(db, name, store=store, country=country)
        if not match:
            diffs.append(
                {
                    "name": name,
                    "receipt_price": receipt_price,
                    "moat_price": None,
                    "delta_pct": None,
                    "flag": "no_moat_match",
                    "product_id": None,
                    "store": store,
                }
            )
            continue
        moat_price = float(match["price"])
        delta_pct = round((receipt_price - moat_price) / moat_price * 100, 1) if moat_price else None
        flag = "match"
        if delta_pct is not None:
            if delta_pct > 5:
                flag = "receipt_higher"
            elif delta_pct < -5:
                flag = "receipt_lower"
        diffs.append(
            {
                "name": name,
                "receipt_price": receipt_price,
                "moat_price": moat_price,
                "delta_pct": delta_pct,
                "flag": flag,
                "product_id": match.get("product_id"),
                "store": match.get("store"),
            }
        )
    return diffs


def submit_receipt(
    db,
    *,
    url: str,
    country: str = "PE",
    username: str | None = None,
    ocr: dict[str, Any] | None = None,
    line_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Persist a receipt submission. OCR may be supplied inline (no raw image stored)."""
    receipt_id = _new_receipt_id()
    country = (country or "PE").strip().upper()
    url = (url or "").strip()

    if ocr is None and line_items:
        ocr = {"line_items": line_items}
    if ocr is None:
        db.execute(
            """
            INSERT INTO receipt_submissions
                (id, username, country, store, image_url, ocr_json, moat_diff_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (receipt_id, username, country, None, url, "{}", "[]", "pending"),
        )
        db.commit()
        return {
            "id": receipt_id,
            "status": "pending",
            "ocr": None,
            "moat_diff": [],
            "contribution": {"updates_moat_confidence": False},
            "message": "OCR pending — supply ocr or line_items, or scan via market_ticket first.",
        }

    line_items = ocr.get("line_items") or line_items or []
    if not line_items:
        db.execute(
            """
            INSERT INTO receipt_submissions
                (id, username, country, store, image_url, ocr_json, moat_diff_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (receipt_id, username, country, ocr.get("store"), url, json.dumps(ocr), "[]", "failed"),
        )
        db.commit()
        return {
            "id": receipt_id,
            "status": "failed",
            "ocr": ocr,
            "moat_diff": [],
            "contribution": {"updates_moat_confidence": False},
            "error": "OCR produced no line items",
        }

    store_key = ocr.get("store_key") or ocr.get("store")
    moat_diff = compute_moat_diff(db, line_items, country=country, store=store_key)
    status = "confirmed" if moat_diff else "failed"
    db.execute(
        """
        INSERT INTO receipt_submissions
            (id, username, country, store, image_url, ocr_json, moat_diff_json, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            receipt_id,
            username,
            country,
            store_key,
            url,
            json.dumps(ocr, ensure_ascii=False),
            json.dumps(moat_diff, ensure_ascii=False),
            status,
        ),
    )
    db.commit()
    return {
        "id": receipt_id,
        "status": status,
        "ocr": ocr,
        "moat_diff": moat_diff,
        "contribution": {"updates_moat_confidence": bool(moat_diff)},
    }


def get_receipt(db, receipt_id: str) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT id, username, country, store, image_url, ocr_json, moat_diff_json, status, created_at
        FROM receipt_submissions WHERE id = ?
        """,
        (receipt_id,),
    ).fetchone()
    if not row:
        return None
    try:
        ocr = json.loads(row["ocr_json"] or "{}")
    except Exception:
        ocr = {}
    try:
        moat_diff = json.loads(row["moat_diff_json"] or "[]")
    except Exception:
        moat_diff = []
    return {
        "id": row["id"],
        "status": row["status"],
        "country": row["country"],
        "store": row["store"],
        "image_url": row["image_url"],
        "ocr": ocr,
        "moat_diff": moat_diff,
        "created_at": row["created_at"],
    }


def crowd_stats_for_product(
    db,
    *,
    product_id: str | None = None,
    store: str | None = None,
    name: str | None = None,
    days: int = CROWD_WINDOW_DAYS,
) -> dict[str, int]:
    """Aggregate crowd confirmations/conflicts from recent receipt submissions."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()
    rows = db.execute(
        """
        SELECT moat_diff_json FROM receipt_submissions
        WHERE status = 'confirmed' AND created_at >= ?
        """,
        (cutoff,),
    ).fetchall()
    confirmations = 0
    conflicts = 0
    product_id = (product_id or "").strip()
    store = (store or "").strip()
    name_l = (name or "").strip().lower()
    for row in rows:
        try:
            diffs = json.loads(row["moat_diff_json"] or "[]")
        except Exception:
            continue
        for diff in diffs:
            if product_id and diff.get("product_id") != product_id:
                continue
            if store and diff.get("store") != store:
                continue
            if name_l and name_l not in str(diff.get("name") or "").lower():
                continue
            flag = diff.get("flag")
            if flag in {"match", "receipt_lower"}:
                confirmations += 1
            elif flag == "receipt_higher":
                conflicts += 1
    return {"crowd_confirmations_7d": confirmations, "crowd_conflicts_7d": conflicts}


def compute_moat_confidence(
    db,
    *,
    product_id: str | None = None,
    store: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Crowd-sourced confidence tier for a product/store pair."""
    stats = crowd_stats_for_product(db, product_id=product_id, store=store, name=name)
    confirmations = stats["crowd_confirmations_7d"]
    conflicts = stats["crowd_conflicts_7d"]
    tier = "unverified"
    if confirmations >= VERIFIED_CONFIRMATIONS:
        tier = "verified"
    elif confirmations > 0:
        tier = "observed"
    if conflicts > confirmations and confirmations > 0:
        tier = "conflicted"
    return {
        "product_id": product_id,
        "store": store,
        "name": name,
        **stats,
        "confidence_tier": tier,
        "verified_threshold": VERIFIED_CONFIRMATIONS,
    }
