"""Billing, subscriptions, and payment schema migrations.

Public pricing (landing + README, 2026-06):
  free          $0   — 1,000 req/day (register + API key)
  starter       $24/mo — 5,000 req/day, export, alerts (no checkout)
  pro           $39/mo — 10,000 req/day, checkout, full MCP
  pro_founding  $29/mo — first 100 seats, Pro capabilities (locked 12m via PayPal plan)
  pro_annual    $390/yr — Pro annual (−17%)
  enterprise    custom

Legacy tier builder remains for DB rows; not on landing.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from . import market_core
from .order_status import InvalidOrderTransition, validate_order_transition

logger = market_core.logger

# Canonical limits — propagate via ops/PRICING-CHANGE-CHECKLIST.md
PUBLIC_FREE_REQ_DAY = 1_000
PUBLIC_STARTER_REQ_DAY = 5_000
PUBLIC_PRO_REQ_DAY = 10_000
PUBLIC_STARTER_PRICE_USD = float(os.getenv("STARTER_PRICE_USD", "24"))
PUBLIC_PRO_PRICE_USD = float(os.getenv("PRO_PRICE_USD", "39"))
PUBLIC_PRO_FOUNDING_PRICE_USD = float(os.getenv("PRO_FOUNDING_PRICE_USD", "29"))
PUBLIC_PRO_ANNUAL_PRICE_USD = float(os.getenv("PRO_ANNUAL_PRICE_USD", "390"))
FOUNDING_PROMO_CODE = os.getenv("FOUNDING_PROMO_CODE", "founding100")
FOUNDING_SEAT_LIMIT = int(os.getenv("FOUNDING_SEAT_LIMIT", "100"))

VALID_BILLING_PLANS = frozenset({"starter", "pro", "pro_founding", "pro_annual"})
PLAN_ALIASES = {"founding": "pro_founding", "annual": "pro_annual", "pro-founding": "pro_founding"}

# Wave 1 feature gates (tier slug → allowed tiers)
FEATURE_TIERS: dict[str, frozenset[str]] = {
    "affordability": frozenset({"free", "starter", "pro", "pro_founding", "pro_annual", "enterprise", "builder"}),
    "tco_delivery": frozenset({"starter", "pro", "pro_founding", "pro_annual", "enterprise", "builder"}),
    "substitutes_3": frozenset({"starter", "pro", "pro_founding", "pro_annual", "enterprise", "builder"}),
    "substitutes_1": frozenset({"free", "starter", "pro", "pro_founding", "pro_annual", "enterprise", "builder"}),
    "optimize_purchase": frozenset({"starter", "pro", "pro_founding", "pro_annual", "enterprise", "builder"}),
    "household_read": frozenset({"starter", "pro", "pro_founding", "pro_annual", "enterprise", "builder"}),
    "household_write": frozenset({"pro", "pro_founding", "pro_annual", "enterprise", "builder"}),
    "receipt_crowd": frozenset({"starter", "pro", "pro_founding", "pro_annual", "enterprise", "builder"}),
    "ecosystem_radar": frozenset({"pro", "pro_founding", "pro_annual", "enterprise", "builder"}),
    "procurement_bulk": frozenset({"enterprise", "builder"}),
}


def feature_allowed(tier: str | None, feature_slug: str) -> bool:
    """Return whether *tier* may use *feature_slug*."""
    allowed = FEATURE_TIERS.get(feature_slug)
    if not allowed:
        return True
    t = (tier or "free").strip().lower()
    return t in allowed or t == "enterprise"


def substitute_limit_for_tier(tier: str | None) -> int:
    return 3 if feature_allowed(tier, "substitutes_3") else 1


def normalize_billing_plan(plan: str) -> str:
    p = (plan or "pro").strip().lower().replace("-", "_")
    p = PLAN_ALIASES.get(p, p)
    return p if p in VALID_BILLING_PLANS else "pro"


def tier_for_billing_plan(plan: str) -> str:
    return "starter" if normalize_billing_plan(plan) == "starter" else "pro"


def price_usd_for_plan(plan: str) -> float:
    p = normalize_billing_plan(plan)
    return {
        "starter": PUBLIC_STARTER_PRICE_USD,
        "pro": PUBLIC_PRO_PRICE_USD,
        "pro_founding": PUBLIC_PRO_FOUNDING_PRICE_USD,
        "pro_annual": PUBLIC_PRO_ANNUAL_PRICE_USD,
    }[p]


def price_label_for_plan(plan: str) -> str:
    p = normalize_billing_plan(plan)
    if p == "pro_annual":
        return f"${PUBLIC_PRO_ANNUAL_PRICE_USD:.0f}/yr"
    return f"${price_usd_for_plan(p):.0f}/mo"


def checkout_upgrade_detail(username: str = "") -> str:
    """Human-readable message explaining why checkout is unavailable.

    When ``username`` is provided, includes the user's current tier so the
    message is diagnostic rather than generic (issue #17).
    """
    if username:
        try:
            sub = db_get_subscription(username)
            tier = sub.get("tier", "free")
            tier_label = tier.replace("_", " ").title()
            if tier in ("pro", "pro_founding", "pro_annual"):
                return "Checkout is enabled on your account. If you see an error, contact soporte@cli-market.dev."
            if tier == "starter":
                return (
                    f"Checkout requires CLI Market Pro ({price_label_for_plan('pro')}). "
                    f"You are on {tier_label} ({price_label_for_plan('starter')}). "
                    "Run: market upgrade pro"
                )
            # free tier
            return (
                f"Checkout requires CLI Market Pro ({price_label_for_plan('pro')}). "
                f"You are on Free tier. Upgrade: market upgrade pro"
            )
        except Exception:
            pass
    return (
        f"Checkout requires CLI Market Pro ({price_label_for_plan('pro')}). "
        "Run: market upgrade"
    )


def checkout_diagnostic(username: str) -> dict:
    """Return structured diagnostic for debugging ghost checkout attempts.

    Tells a support operator exactly why a checkout attempt failed or
    would fail for a given user.
    """
    try:
        sub = db_get_subscription(username)
    except Exception:
        return {"username": username, "error": "could not read subscription"}

    tier = sub.get("tier", "free")
    tier_cfg = TIERS.get(tier, TIERS["free"])
    legacy = os.getenv("MARKET_LEGACY_CHECKOUT", "").lower() in ("1", "true", "yes")

    return {
        "username": username,
        "tier": tier,
        "tier_label": tier.replace("_", " ").title(),
        "checkout_enabled": bool(tier_cfg.get("checkout")),
        "legacy_bypass": legacy,
        "can_checkout": user_can_checkout(username),
        "upgrade_to": "pro" if tier != "pro" else None,
        "upgrade_price": price_label_for_plan("pro") if tier != "pro" else None,
    }

TIERS = {
    "free": {
        "req_min": 60,
        "req_day": 1_000,
        "api_keys": 1,
        "checkout": False,
        "agent_queries_month": 0,
        "history_days": 7,
        "alerts": 0,
        "export": False,
    },
    "starter": {
        "req_min": 120,
        "req_day": 5_000,
        "api_keys": 3,
        "checkout": False,
        "agent_queries_month": 50,
        "history_days": 30,
        "alerts": 3,
        "export": True,        # CSV básico hasta 10k filas
        "white_label": False,
    },
    "pro": {
        "req_min": 300,
        "req_day": 10_000,
        "api_keys": 10,
        "checkout": True,
        "agent_queries_month": -1,   # -1 = ilimitado
        "history_days": 365,
        "alerts": 10,
        "export": True,
        "white_label": False,
    },
    "builder": {
        "req_min": 600,
        "req_day": 50_000,
        "api_keys": 25,
        "checkout": True,
        "agent_queries_month": -1,
        "history_days": -1,          # historial completo
        "alerts": -1,                # sin límite
        "export": True,
        "white_label": True,         # branding propio permitido
    },
    "enterprise": {
        "req_min": -1,               # -1 = sin límite
        "req_day": -1,
        "api_keys": -1,
        "checkout": True,
        "agent_queries_month": -1,
        "history_days": -1,
        "alerts": -1,
        "export": True,
    },
}


def _migrate_payment_schema(db) -> None:
    """Add payment columns/tables on existing deployments."""
    if market_core.USE_PG:
        db.execute("SET lock_timeout = '5s'")
        db.execute("""
            CREATE TABLE IF NOT EXISTS subscription_requests (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                payment_link TEXT DEFAULT '',
                email_sent INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sub_req_email ON subscription_requests(email)"
        )
        db.execute("""
            CREATE TABLE IF NOT EXISTS billing_pending (
                external_id TEXT PRIMARY KEY,
                gateway TEXT NOT NULL,
                username TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'subscription',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS promo_redemptions (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                promo_code TEXT NOT NULL,
                plan_slug TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events_processed (
                event_key TEXT PRIMARY KEY,
                source TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_promo_redemptions_code ON promo_redemptions(promo_code)"
        )
        for stmt in (
            "ALTER TABLE app_orders ADD COLUMN IF NOT EXISTS gateway_ref TEXT DEFAULT ''",
            "ALTER TABLE app_orders ADD COLUMN IF NOT EXISTS idempotency_key TEXT DEFAULT ''",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS paypal_subscription_id TEXT DEFAULT ''",
            "ALTER TABLE subscription_requests ADD COLUMN IF NOT EXISTS display_name TEXT DEFAULT ''",
        ):
            try:
                db.execute(stmt)
            except Exception as e:
                logger.warning("PG migration skipped: %s", e)
        try:
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_order_idempotency "
                "ON app_orders(username, idempotency_key) "
                "WHERE idempotency_key IS NOT NULL AND idempotency_key != ''"
            )
        except Exception as e:
            logger.warning("PG idempotency index skipped: %s", e)
        return
    db.execute("""
        CREATE TABLE IF NOT EXISTS billing_pending (
            external_id TEXT PRIMARY KEY,
            gateway TEXT NOT NULL,
            username TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'subscription',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS promo_redemptions (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            promo_code TEXT NOT NULL,
            plan_slug TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS webhook_events_processed (
            event_key TEXT PRIMARY KEY,
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_promo_redemptions_code ON promo_redemptions(promo_code)"
    )
    for stmt in (
        "ALTER TABLE app_orders ADD COLUMN gateway_ref TEXT DEFAULT ''",
        "ALTER TABLE app_orders ADD COLUMN idempotency_key TEXT DEFAULT ''",
        "ALTER TABLE subscriptions ADD COLUMN paypal_subscription_id TEXT DEFAULT ''",
        "ALTER TABLE subscription_requests ADD COLUMN display_name TEXT DEFAULT ''",
    ):
        try:
            db.execute(stmt)
        except Exception:
            pass
    try:
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_order_idempotency "
            "ON app_orders(username, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL AND idempotency_key != ''"
        )
    except Exception:
        pass
    db.execute("""
        CREATE TABLE IF NOT EXISTS subscription_requests (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            payment_link TEXT DEFAULT '',
            email_sent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_sub_req_email ON subscription_requests(email)"
    )


def _is_expired(expires_at) -> bool:
    """True if expires_at (str or datetime, any backend) is in the past."""
    if not expires_at:
        return False
    try:
        s = str(expires_at).replace("Z", "+00:00")
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        dt = datetime.fromisoformat(s)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt < datetime.now(timezone.utc)
    except ValueError:
        return False


def db_get_subscription(username: str) -> dict:
    """Get user subscription. Falls back to free tier defaults.

    A subscription whose expires_at has passed (e.g. a referral-granted
    free Pro month) is treated as expired back to free, without needing a
    separate cron to downgrade the row.
    """
    db = market_core.get_db()
    row = db.execute(
        "SELECT tier, req_limit_day, req_limit_min, expires_at FROM subscriptions WHERE username=?",
        (username,),
    ).fetchone()
    db.close()
    if row and not _is_expired(row["expires_at"]):
        base = dict(row)
    else:
        base = {
            "tier": "free",
            "req_limit_day": TIERS["free"]["req_day"],
            "req_limit_min": TIERS["free"]["req_min"],
        }
    # Enrich with tier capabilities so callers don't need to re-lookup TIERS.
    tier_cfg = TIERS.get(base["tier"], TIERS["free"])
    base.setdefault("agent_queries_month", tier_cfg["agent_queries_month"])
    base.setdefault("history_days", tier_cfg["history_days"])
    base.setdefault("alerts", tier_cfg["alerts"])
    base.setdefault("export", tier_cfg["export"])
    return base


def db_set_subscription(
    username: str,
    tier: str,
    req_day: int | None = None,
    req_min: int | None = None,
    expires_days: int | None = None,
    paypal_subscription_id: str | None = None,
) -> dict:
    """Set a user's subscription tier.

    `expires_days` set to an int makes this grant temporary (e.g. a
    referral-earned free Pro month); omit it (None) for a permanent grant
    — every call explicitly clears any prior expiry so a permanent grant
    (paid Pro, lifetime referral reward, etc.) never inherits a stale
    expires_at from an earlier temporary one.
    """
    db = market_core.get_db()
    t = TIERS.get(tier, TIERS["free"])
    day = req_day if req_day is not None else t["req_day"]
    mn = req_min if req_min is not None else t["req_min"]
    pp_sub = paypal_subscription_id or ""
    expires_at = (
        (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
        if expires_days is not None
        else None
    )
    db.execute(
        "INSERT INTO subscriptions (username, tier, req_limit_day, req_limit_min, expires_at, paypal_subscription_id) "
        "VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(username) DO UPDATE SET tier=?, req_limit_day=?, req_limit_min=?, expires_at=?, "
        "paypal_subscription_id=CASE WHEN excluded.paypal_subscription_id != '' "
        "THEN excluded.paypal_subscription_id ELSE subscriptions.paypal_subscription_id END",
        (username, tier, day, mn, expires_at, pp_sub, tier, day, mn, expires_at),
    )
    db.commit()
    db.close()
    return {"username": username, "tier": tier, "req_limit_day": day, "req_limit_min": mn, "expires_at": expires_at}


def db_claim_webhook_event(event_key: str, source: str = "") -> bool:
    """Return True if this is the first time we process event_key."""
    key = (event_key or "").strip()
    if not key:
        return True
    db = market_core.get_db()
    if market_core.USE_PG:
        cur = db.execute(
            "INSERT INTO webhook_events_processed (event_key, source) VALUES (?,?) "
            "ON CONFLICT (event_key) DO NOTHING",
            (key, source),
        )
        db.commit()
        claimed = cur.rowcount > 0
    else:
        cur = db.execute(
            "INSERT OR IGNORE INTO webhook_events_processed (event_key, source) VALUES (?,?)",
            (key, source),
        )
        db.commit()
        claimed = cur.rowcount > 0
    db.close()
    return claimed


def db_find_order_by_idempotency_key(username: str, idempotency_key: str) -> dict | None:
    key = (idempotency_key or "").strip()
    if not key:
        return None
    db = market_core.get_db()
    row = db.execute(
        "SELECT order_id, username, payment_method, total, status, gateway_ref, idempotency_key "
        "FROM app_orders WHERE username=? AND idempotency_key=?",
        (username, key),
    ).fetchone()
    db.close()
    return dict(row) if row else None


def db_set_order_status(order_id: str, status: str) -> bool:
    """Update order status with canonical transition validation."""
    db = market_core.get_db()
    row = db.execute(
        "SELECT status FROM app_orders WHERE order_id=?",
        (order_id,),
    ).fetchone()
    if not row:
        db.close()
        return False
    try:
        validate_order_transition(row["status"], status)
    except InvalidOrderTransition:
        db.close()
        raise
    cur = db.execute("UPDATE app_orders SET status=? WHERE order_id=?", (status, order_id))
    db.commit()
    affected = cur.rowcount
    db.close()
    return affected > 0


def db_update_order_status(order_id: str, status: str) -> bool:
    """Backward-compatible alias for db_set_order_status."""
    return db_set_order_status(order_id, status)


def db_set_order_gateway_ref(order_id: str, gateway_ref: str) -> None:
    db = market_core.get_db()
    db.execute("UPDATE app_orders SET gateway_ref=? WHERE order_id=?", (gateway_ref, order_id))
    db.commit()
    db.close()


def db_find_order_by_gateway_ref(gateway_ref: str) -> dict | None:
    db = market_core.get_db()
    row = db.execute(
        "SELECT order_id, username, payment_method, total, status FROM app_orders WHERE gateway_ref=?",
        (gateway_ref,),
    ).fetchone()
    db.close()
    return dict(row) if row else None


def db_find_order_by_id(order_id: str) -> dict | None:
    db = market_core.get_db()
    row = db.execute(
        "SELECT order_id, username, payment_method, total, status, gateway_ref FROM app_orders "
        "WHERE order_id=?",
        (order_id,),
    ).fetchone()
    db.close()
    return dict(row) if row else None


def db_save_billing_pending(
    external_id: str, gateway: str, username: str, kind: str = "subscription"
) -> None:
    db = market_core.get_db()
    if market_core.USE_PG:
        db.execute(
            "INSERT INTO billing_pending (external_id, gateway, username, kind) VALUES (?,?,?,?) "
            "ON CONFLICT (external_id) DO UPDATE SET username=excluded.username, kind=excluded.kind",
            (external_id, gateway, username, kind),
        )
    else:
        db.execute(
            "INSERT OR REPLACE INTO billing_pending (external_id, gateway, username, kind) "
            "VALUES (?,?,?,?)",
            (external_id, gateway, username, kind),
        )
    db.commit()
    db.close()


def db_get_billing_pending(external_id: str) -> dict | None:
    db = market_core.get_db()
    row = db.execute(
        "SELECT external_id, gateway, username, kind FROM billing_pending WHERE external_id=?",
        (external_id,),
    ).fetchone()
    db.close()
    return dict(row) if row else None


def db_delete_billing_pending(external_id: str) -> None:
    db = market_core.get_db()
    db.execute("DELETE FROM billing_pending WHERE external_id=?", (external_id,))
    db.commit()
    db.close()


def db_count_promo_redemptions(promo_code: str) -> int:
    db = market_core.get_db()
    row = db.execute(
        "SELECT COUNT(*) AS n FROM promo_redemptions WHERE promo_code=?",
        (promo_code,),
    ).fetchone()
    db.close()
    return int(row["n"] if row else 0)


def db_has_promo_redemption(username: str, promo_code: str) -> bool:
    db = market_core.get_db()
    row = db.execute(
        "SELECT 1 FROM promo_redemptions WHERE username=? AND promo_code=? LIMIT 1",
        (username, promo_code),
    ).fetchone()
    db.close()
    return row is not None


def db_record_promo_redemption(username: str, promo_code: str, plan_slug: str) -> dict:
    rid = f"PROMO-{uuid.uuid4().hex[:8].upper()}"
    db = market_core.get_db()
    db.execute(
        "INSERT INTO promo_redemptions (id, username, promo_code, plan_slug) VALUES (?,?,?,?)",
        (rid, username, promo_code, plan_slug),
    )
    db.commit()
    db.close()
    return {"id": rid, "username": username, "promo_code": promo_code, "plan_slug": plan_slug}


def validate_founding_available(username: str, promo_code: str = "") -> tuple[bool, str]:
    """Return (ok, error_message). founding100 promo required unless seats remain."""
    code = (promo_code or FOUNDING_PROMO_CODE).strip().lower()
    if code != FOUNDING_PROMO_CODE.lower():
        return False, f"Invalid founding promo code (expected {FOUNDING_PROMO_CODE})"
    if db_has_promo_redemption(username, code):
        return True, ""
    used = db_count_promo_redemptions(code)
    if used >= FOUNDING_SEAT_LIMIT:
        return False, f"Founding offer full ({FOUNDING_SEAT_LIMIT} seats)"
    return True, ""


def founding_seats_remaining() -> int:
    used = db_count_promo_redemptions(FOUNDING_PROMO_CODE)
    return max(0, FOUNDING_SEAT_LIMIT - used)


# ── Referral rewards (market share — docs/market-share-spec.md) ───────────────
#
# Per-activation: +500 req/day for the referrer, while still on the free
# tier. Tier thresholds grant Pro (temporarily at 3, permanently at 10).
# 25+ is Enterprise preview + swag — not gradable automatically (physical
# swag), so it's only recorded as a promo redemption for manual ops
# fulfillment rather than applied as a tier change.
REFERRAL_BONUS_PER_ACTIVATION = 500
REFERRAL_TIER_REWARDS: dict[int, tuple[str, int | None]] = {
    3: ("pro", 30),    # 1 month free Pro
    10: ("pro", None),  # Pro lifetime
}
REFERRAL_ENTERPRISE_THRESHOLD = 25


def apply_referral_activation(ref_code: str, new_username: str) -> dict | None:
    """Credit a referrer when someone they referred completes registration.

    Called from POST /auth/register when the new signup supplies a
    ref_code. Increments the code's activated_count and grants rewards;
    each tier reward is granted at most once per referrer (tracked via
    promo_redemptions) so re-crossing a threshold is a no-op.
    """
    code = (ref_code or "").strip()[:16]
    if not code:
        return None

    db = market_core.get_db()
    try:
        row = db.execute(
            "SELECT username FROM referral_codes WHERE ref_code=?", (code,)
        ).fetchone()
        if not row or not row["username"] or row["username"] == new_username:
            return None  # unknown code, or self-referral
        referrer = row["username"]

        db.execute(
            "UPDATE referral_codes SET activated_count = activated_count + 1 WHERE ref_code=?",
            (code,),
        )
        db.commit()
        count_row = db.execute(
            "SELECT activated_count FROM referral_codes WHERE ref_code=?", (code,)
        ).fetchone()
        count = int(count_row["activated_count"])
    finally:
        db.close()

    sub = db_get_subscription(referrer)
    if (sub.get("tier") or "free") == "free":
        bumped_day = int(sub.get("req_limit_day") or TIERS["free"]["req_day"]) + REFERRAL_BONUS_PER_ACTIVATION
        db_set_subscription(referrer, "free", req_day=bumped_day)

    for threshold in sorted(REFERRAL_TIER_REWARDS):
        if count < threshold:
            continue
        promo_code = f"referral_tier_{threshold}"
        if db_has_promo_redemption(referrer, promo_code):
            continue
        tier, expires_days = REFERRAL_TIER_REWARDS[threshold]
        db_set_subscription(referrer, tier, expires_days=expires_days)
        db_record_promo_redemption(referrer, promo_code, tier)

    if count >= REFERRAL_ENTERPRISE_THRESHOLD:
        promo_code = "referral_tier_25"
        if not db_has_promo_redemption(referrer, promo_code):
            db_record_promo_redemption(referrer, promo_code, "enterprise_preview_manual")

    return {"referrer": referrer, "activated_count": count}


def user_can_checkout(username: str) -> bool:
    """True if user tier allows checkout or legacy bypass is enabled."""
    if os.getenv("MARKET_LEGACY_CHECKOUT", "").lower() in ("1", "true", "yes"):
        return True
    sub = db_get_subscription(username)
    return bool(TIERS.get(sub.get("tier", "free"), TIERS["free"]).get("checkout"))


def db_get_user_email(username: str) -> str | None:
    """Return the email associated with a username from subscription_requests, or None."""
    db = market_core.get_db()
    row = db.execute(
        "SELECT email FROM subscription_requests WHERE username=? ORDER BY created_at DESC LIMIT 1",
        (username,),
    ).fetchone()
    db.close()
    return row["email"] if row else None


def db_create_subscription_request(
    username: str,
    email: str,
    payment_link: str,
    *,
    prefix: str = "PRO",
    display_name: str = "",
) -> dict:
    req_id = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
    dn = (display_name or "").strip()
    db = market_core.get_db()
    db.execute(
        """
        INSERT INTO subscription_requests (id, username, email, display_name, status, payment_link, email_sent)
        VALUES (?, ?, ?, ?, 'pending', ?, 0)
        """,
        (req_id, username, email.strip().lower(), dn, payment_link),
    )
    db.commit()
    db.close()
    return {
        "id": req_id,
        "username": username,
        "email": email.strip().lower(),
        "display_name": dn,
        "payment_link": payment_link,
    }


def db_get_latest_subscription_request_for_user(username: str) -> dict | None:
    db = market_core.get_db()
    row = db.execute(
        """
        SELECT id, username, email, display_name, status, payment_link, email_sent, created_at
        FROM subscription_requests
        WHERE username=?
        ORDER BY created_at DESC LIMIT 1
        """,
        (username.strip(),),
    ).fetchone()
    db.close()
    return dict(row) if row else None


def db_mark_subscription_request_emailed(request_id: str) -> None:
    db = market_core.get_db()
    db.execute(
        "UPDATE subscription_requests SET email_sent=1 WHERE id=?",
        (request_id,),
    )
    db.commit()
    db.close()


def db_update_subscription_request_payment_link(request_id: str, payment_link: str) -> bool:
    """Persist checkout URL or payment note on a pending subscription request."""
    db = market_core.get_db()
    cur = db.execute(
        "UPDATE subscription_requests SET payment_link=? WHERE id=? AND status='pending'",
        (payment_link.strip(), request_id),
    )
    db.commit()
    updated = cur.rowcount > 0
    db.close()
    return updated


def db_update_subscription_request_display_name(request_id: str, display_name: str) -> bool:
    """Persist friendly name on a subscription request (checkout or ops override)."""
    dn = (display_name or "").strip()
    if not dn:
        return False
    db = market_core.get_db()
    cur = db.execute(
        "UPDATE subscription_requests SET display_name=? WHERE id=?",
        (dn, request_id),
    )
    db.commit()
    updated = cur.rowcount > 0
    db.close()
    return updated


def db_recent_subscription_request(email: str, hours: int = 24) -> dict | None:
    db = market_core.get_db()
    row = db.execute(
        """
        SELECT id, username, email, display_name, status, payment_link, email_sent, created_at
        FROM subscription_requests
        WHERE email=?
        ORDER BY created_at DESC LIMIT 1
        """,
        (email.strip().lower(),),
    ).fetchone()
    db.close()
    if not row:
        return None
    row = dict(row)
    created = row.get("created_at")
    if created and hours > 0:
        try:
            if isinstance(created, str):
                ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
            else:
                ts = created
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - ts > timedelta(hours=hours):
                return None
        except (ValueError, TypeError):
            pass
    return row


def db_find_subscription_request(*, request_id: str = "", email: str = "") -> dict | None:
    db = market_core.get_db()
    if request_id:
        row = db.execute(
            "SELECT id, username, email, display_name, status, payment_link, email_sent, created_at "
            "FROM subscription_requests WHERE id=?",
            (request_id,),
        ).fetchone()
    elif email:
        row = db.execute(
            "SELECT id, username, email, display_name, status, payment_link, email_sent, created_at "
            "FROM subscription_requests WHERE email=? ORDER BY created_at DESC LIMIT 1",
            (email.strip().lower(),),
        ).fetchone()
    else:
        db.close()
        return None
    db.close()
    return dict(row) if row else None


def db_mark_subscription_requests_activated_for_user(username: str) -> int:
    """Mark all pending Pro requests for username as activated (post PayPal webhook)."""
    db = market_core.get_db()
    cur = db.execute(
        "UPDATE subscription_requests SET status='activated' WHERE username=? AND status='pending'",
        (username.strip(),),
    )
    db.commit()
    count = cur.rowcount
    db.close()
    return count


def db_mark_subscription_request_activated(request_id: str, username: str = "") -> bool:
    db = market_core.get_db()
    if username:
        cur = db.execute(
            "UPDATE subscription_requests SET status='activated', username=? WHERE id=?",
            (username, request_id),
        )
    else:
        cur = db.execute(
            "UPDATE subscription_requests SET status='activated' WHERE id=?",
            (request_id,),
        )
    db.commit()
    updated = cur.rowcount > 0
    db.close()
    return updated
