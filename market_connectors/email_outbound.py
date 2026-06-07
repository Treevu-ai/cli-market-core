"""Outbound email for billing and onboarding (stdlib SMTP)."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

FROM_EMAIL = os.getenv("BILLING_FROM_EMAIL", "hello@cli-market.dev")
FROM_NAME = os.getenv("BILLING_FROM_NAME", "CLI Market")
NOTIFY_EMAIL = os.getenv("BILLING_NOTIFY_EMAIL", "hello@cli-market.dev")
PRO_PAYMENT_URL = os.getenv(
    "PRO_PAYMENT_URL",
    "https://www.paypal.com/ncp/payment/B6YVFTG4MA73J",
)
PRO_PRICE_LABEL = os.getenv("PRO_PRICE_LABEL", "$79/month")
STARTER_PRICE_LABEL = os.getenv("STARTER_PRICE_LABEL", "$29/month")


def _smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def send_pro_payment_email(
    *,
    to_email: str,
    username: str,
    request_id: str,
    lang: str = "en",
) -> dict:
    """Email subscriber with Pro plan details and payment link."""
    payment_url = PRO_PAYMENT_URL
    user_line_es = f"Usuario: <strong>{username}</strong>" if username else "Usuario: el que usaste en <code>market login</code>"
    user_line_en = f"Username: <strong>{username}</strong>" if username else "Username: the one you used in <code>market login</code>"
    user_plain_es = f"Usuario: {username}" if username else "Usuario: el que usaste en `market login`"
    user_plain_en = f"Username: {username}" if username else "Username: the one from `market login`"

    if lang == "es":
        subject = f"Tu acceso Pro está casi listo — CLI Market"
        text = f"""Hola{f' {username}' if username else ''},

Recibimos tu solicitud de CLI Market Pro. Un paso más y tendrás acceso completo.

──────────────────────────────
Plan Pro — {PRO_PRICE_LABEL}
• 10,000 consultas API / día
• 10 claves API (lectura + escritura)
• Exportación JSON/CSV
• Checkout automatizado con PayPal + Yape/Plin
──────────────────────────────

PAGA AQUÍ → {payment_url}

Después de pagar, responde a este correo con:
  1. {user_plain_es}
  2. Referencia: {request_id}

Si pagó con el botón alojado de PayPal (flujo manual), activamos Pro en ≤24 h hábiles y le confirmamos por email.

¿Prefiere activación automática? Use la suscripción PayPal en https://cli-market.dev/#pricing — Pro se activa en segundos vía webhook.

¿Preguntas? Responde este correo — contestamos el mismo día.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0b;font-family:ui-sans-serif,system-ui,sans-serif;color:#e5e2e3;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0b;padding:40px 0;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#131314;border:1px solid #3b4a44;border-radius:12px;overflow:hidden;max-width:560px;width:100%;">
      <tr><td style="padding:32px 36px 0;">
        <p style="margin:0 0 4px;font-family:monospace;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:#3afecf;">CLI MARKET PRO</p>
        <h1 style="margin:0 0 24px;font-size:22px;font-weight:700;color:#fff;line-height:1.3;">Tu acceso Pro está casi listo</h1>
        <p style="margin:0 0 20px;font-size:14px;color:#b9cac2;line-height:1.6;">
          Hola{f' <strong style="color:#fff">{username}</strong>' if username else ''},<br><br>
          Recibimos tu solicitud. Un paso más y tendrás acceso completo a CLI Market Pro.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#1c1b1c;border:1px solid #3b4a44;border-radius:8px;margin-bottom:24px;">
          <tr><td style="padding:20px 24px;">
            <p style="margin:0 0 12px;font-size:13px;font-weight:700;color:#fff;">{PRO_PRICE_LABEL} · Plan Pro incluye:</p>
            <p style="margin:0;font-size:13px;color:#b9cac2;line-height:1.8;">
              ✓ 10,000 consultas API / día<br>
              ✓ 10 claves API (lectura + escritura)<br>
              ✓ Exportación JSON/CSV<br>
              ✓ Checkout con PayPal + Yape/Plin
            </p>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="padding:0 36px 24px;" align="center">
        <a href="{payment_url}" style="display:inline-block;background:#3afecf;color:#002118;font-family:monospace;font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;padding:14px 32px;border-radius:4px;text-decoration:none;">Pagar ahora →</a>
      </td></tr>
      <tr><td style="padding:0 36px 32px;">
        <p style="margin:0 0 12px;font-size:13px;font-weight:600;color:#fff;">Después de pagar, responde este correo con:</p>
        <table cellpadding="0" cellspacing="0" style="font-size:13px;color:#b9cac2;">
          <tr><td style="padding:3px 0;">1.&nbsp;</td><td>{user_line_es}</td></tr>
          <tr><td style="padding:3px 0;">2.&nbsp;</td><td>Referencia: <code style="background:#1c1b1c;padding:1px 6px;border-radius:3px;color:#3afecf;">{request_id}</code></td></tr>
        </table>
        <p style="margin:20px 0 0;font-size:13px;color:#b9cac2;line-height:1.6;">
          Flujo manual (botón alojado): activación en <strong style="color:#fff">≤24 h hábiles</strong>.<br>
          Suscripción PayPal en cli-market.dev: activación automática en segundos.<br>
          ¿Preguntas? Responde este correo — contestamos el mismo día.
        </p>
      </td></tr>
      <tr><td style="padding:20px 36px;border-top:1px solid #3b4a44;">
        <p style="margin:0;font-size:12px;color:#b9cac2;">— Ricardo · CLI Market · <a href="mailto:hello@cli-market.dev" style="color:#3afecf;text-decoration:none;">hello@cli-market.dev</a></p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""
    else:
        subject = f"Your Pro access is one step away — CLI Market"
        text = f"""Hi{f' {username}' if username else ''},

We received your CLI Market Pro request. One more step and you're in.

──────────────────────────────
Pro plan — {PRO_PRICE_LABEL}
• 10,000 API requests / day
• 10 API keys (read + write)
• JSON/CSV export
• Automated checkout with PayPal + Yape/Plin
──────────────────────────────

PAY HERE → {payment_url}

After payment, reply to this email with:
  1. {user_plain_en}
  2. Reference: {request_id}

If you paid via the hosted PayPal button (manual flow), we activate Pro within 24 business hours and confirm by email.

Prefer instant activation? Use PayPal subscription at https://cli-market.dev/#pricing — Pro activates in seconds via webhook.

Questions? Reply to this email — we respond same day.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0b;font-family:ui-sans-serif,system-ui,sans-serif;color:#e5e2e3;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0b;padding:40px 0;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#131314;border:1px solid #3b4a44;border-radius:12px;overflow:hidden;max-width:560px;width:100%;">
      <tr><td style="padding:32px 36px 0;">
        <p style="margin:0 0 4px;font-family:monospace;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:#3afecf;">CLI MARKET PRO</p>
        <h1 style="margin:0 0 24px;font-size:22px;font-weight:700;color:#fff;line-height:1.3;">Your Pro access is one step away</h1>
        <p style="margin:0 0 20px;font-size:14px;color:#b9cac2;line-height:1.6;">
          Hi{f' <strong style="color:#fff">{username}</strong>' if username else ''},<br><br>
          We received your request. One more step and you'll have full access to CLI Market Pro.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#1c1b1c;border:1px solid #3b4a44;border-radius:8px;margin-bottom:24px;">
          <tr><td style="padding:20px 24px;">
            <p style="margin:0 0 12px;font-size:13px;font-weight:700;color:#fff;">{PRO_PRICE_LABEL} · Pro plan includes:</p>
            <p style="margin:0;font-size:13px;color:#b9cac2;line-height:1.8;">
              ✓ 10,000 API requests / day<br>
              ✓ 10 API keys (read + write)<br>
              ✓ JSON/CSV export<br>
              ✓ Checkout with PayPal + Yape/Plin
            </p>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="padding:0 36px 24px;" align="center">
        <a href="{payment_url}" style="display:inline-block;background:#3afecf;color:#002118;font-family:monospace;font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;padding:14px 32px;border-radius:4px;text-decoration:none;">Pay now →</a>
      </td></tr>
      <tr><td style="padding:0 36px 32px;">
        <p style="margin:0 0 12px;font-size:13px;font-weight:600;color:#fff;">After paying, reply to this email with:</p>
        <table cellpadding="0" cellspacing="0" style="font-size:13px;color:#b9cac2;">
          <tr><td style="padding:3px 0;">1.&nbsp;</td><td>{user_line_en}</td></tr>
          <tr><td style="padding:3px 0;">2.&nbsp;</td><td>Reference: <code style="background:#1c1b1c;padding:1px 6px;border-radius:3px;color:#3afecf;">{request_id}</code></td></tr>
        </table>
        <p style="margin:20px 0 0;font-size:13px;color:#b9cac2;line-height:1.6;">
          We activate your account in <strong style="color:#fff">under 24 hours</strong> and confirm by email.<br>
          Questions? Reply to this email — we respond same day.
        </p>
      </td></tr>
      <tr><td style="padding:20px 36px;border-top:1px solid #3b4a44;">
        <p style="margin:0;font-size:12px;color:#b9cac2;">— Ricardo · CLI Market · <a href="mailto:hello@cli-market.dev" style="color:#3afecf;text-decoration:none;">hello@cli-market.dev</a></p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""
    return _send(to_email, subject, text, html)


def send_credentials_email(
    *,
    to_email: str,
    username: str,
    api_key: str,
    plan: str = "pro",
    lang: str = "en",
) -> dict:
    """Send API key + credentials to the user after account activation.

    Used for both Pro (after payment confirmed) and Starter (trial start).
    The raw key is shown once — it is the caller's responsibility to only
    call this immediately after key generation.
    """
    is_pro = plan == "pro"
    if lang == "es":
        subject = (
            "Tu API key Pro de CLI Market — guárdala ahora"
            if is_pro else
            "Tu prueba gratuita de CLI Market — API key lista"
        )
        plan_label = "Pro — $79/mes" if is_pro else "Starter — $29/mes (activación manual)"
        limits = (
            "• 10,000 consultas / día\n"
            "• 10 claves API (lectura + escritura)\n"
            "• Exportación JSON/CSV\n"
            "• Checkout con PayPal + Yape/Plin"
            if is_pro else
            "• 5,000 consultas / día\n"
            "• 3 claves API (solo lectura)\n"
            "• Exportación CSV básica\n"
            "• Soporte email 48 h"
        )
        text = f"""Hola {username},

{'Tu cuenta Pro está activa.' if is_pro else 'Su plan Starter está activo.'}

API KEY (¡guárdala ahora — no se vuelve a mostrar!):
{api_key}

──────────────────────────────
{plan_label}:
{limits}
──────────────────────────────

Cómo usarla:

  pip install cli-market
  market login --key {api_key}

O exporta la variable de entorno:
  export MARKET_API_KEY={api_key}

Docs y ejemplos: https://pypi.org/project/cli-market/

¿Preguntas? Responde este correo — contestamos el mismo día.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html_title = "Tu API key Pro está lista" if is_pro else "Su plan Starter está activo"
        html_badge = "CLI MARKET PRO" if is_pro else "CLI MARKET STARTER"
        html_intro = (
            f"Hola <strong style=\"color:#fff\">{username}</strong>,<br><br>"
            f"{'Tu cuenta Pro está activa.' if is_pro else 'Su plan Starter está activo.'} "
            f"Aquí está tu API key — <strong style=\"color:#fff\">muéstrala solo ahora</strong>."
        )
        html_footer_note = "Starter · Activación manual · Sin checkout instantáneo" if not is_pro else ""
    else:
        subject = (
            "Your CLI Market Pro API key — save it now"
            if is_pro else
            "Your CLI Market Starter trial — API key ready"
        )
        plan_label = "Pro — $79/month" if is_pro else "Starter — $29/mo (manual activation)"
        limits = (
            "• 10,000 requests / day\n"
            "• 10 API keys (read + write)\n"
            "• JSON/CSV export\n"
            "• Checkout with PayPal + Yape/Plin"
            if is_pro else
            "• 5,000 requests / day\n"
            "• 3 API keys (read-only)\n"
            "• Basic CSV export\n"
            "• Email support 48 h"
        )
        text = f"""Hi {username},

{'Your Pro account is now active.' if is_pro else 'Your Starter plan is now active.'}

API KEY (save it now — won't be shown again!):
{api_key}

──────────────────────────────
{plan_label}:
{limits}
──────────────────────────────

How to use it:

  pip install cli-market
  market login --key {api_key}

Or set the environment variable:
  export MARKET_API_KEY={api_key}

Docs and examples: https://pypi.org/project/cli-market/

Questions? Reply to this email — we respond same day.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html_title = "Your Pro API key is ready" if is_pro else "Your Starter plan is active"
        html_badge = "CLI MARKET PRO" if is_pro else "CLI MARKET STARTER"
        html_intro = (
            f"Hi <strong style=\"color:#fff\">{username}</strong>,<br><br>"
            f"{'Your Pro account is active.' if is_pro else 'Your Starter plan is active.'} "
            f"Here's your API key — <strong style=\"color:#fff\">this is the only time it'll be shown</strong>."
        )
        html_footer_note = "Starter · Manual activation · No instant checkout" if not is_pro else ""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0b;font-family:ui-sans-serif,system-ui,sans-serif;color:#e5e2e3;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0b;padding:40px 0;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#131314;border:1px solid #3b4a44;border-radius:12px;overflow:hidden;max-width:560px;width:100%;">
      <tr><td style="padding:32px 36px 0;">
        <p style="margin:0 0 4px;font-family:monospace;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:#3afecf;">{html_badge}</p>
        <h1 style="margin:0 0 24px;font-size:22px;font-weight:700;color:#fff;line-height:1.3;">{html_title}</h1>
        <p style="margin:0 0 20px;font-size:14px;color:#b9cac2;line-height:1.6;">{html_intro}</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0b;border:2px solid #3afecf;border-radius:8px;margin-bottom:24px;">
          <tr><td style="padding:16px 20px;">
            <p style="margin:0 0 6px;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#3afecf;">API KEY</p>
            <code style="display:block;font-family:monospace;font-size:13px;color:#fff;word-break:break-all;line-height:1.5;">{api_key}</code>
          </td></tr>
        </table>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#1c1b1c;border:1px solid #3b4a44;border-radius:8px;margin-bottom:24px;">
          <tr><td style="padding:20px 24px;">
            <p style="margin:0 0 12px;font-size:13px;font-weight:700;color:#fff;">{plan_label}</p>
            <p style="margin:0;font-size:13px;color:#b9cac2;line-height:1.8;">{limits.replace(chr(10), '<br>')}</p>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="padding:0 36px 32px;">
        <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#fff;">{"Cómo usarla:" if lang == "es" else "How to use it:"}</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0b;border:1px solid #3b4a44;border-radius:6px;margin-bottom:16px;">
          <tr><td style="padding:12px 16px;font-family:monospace;font-size:12px;color:#b9cac2;line-height:1.8;">
            pip install cli-market<br>
            market login --key {api_key[:20]}...
          </td></tr>
        </table>
        {f'<p style="margin:0 0 0;font-size:12px;color:#b9cac2;text-align:center;">{html_footer_note}</p>' if html_footer_note else ''}
      </td></tr>
      <tr><td style="padding:20px 36px;border-top:1px solid #3b4a44;">
        <p style="margin:0;font-size:12px;color:#b9cac2;">— Ricardo · CLI Market · <a href="mailto:hello@cli-market.dev" style="color:#3afecf;text-decoration:none;">hello@cli-market.dev</a></p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""
    return _send(to_email, subject, text, html)


def send_pro_subscribe_pending_email(
    *,
    to_email: str,
    username: str,
    approve_url: str,
    request_id: str = "",
    lang: str = "en",
) -> dict:
    """Email after PayPal subscription is created — confirm in PayPal, auto-activates via webhook."""
    ref_line_es = f"\nReferencia: {request_id}" if request_id else ""
    ref_line_en = f"\nReference: {request_id}" if request_id else ""

    if lang == "es":
        subject = "Confirme su suscripción Pro en PayPal — CLI Market"
        text = f"""Hola {username},

Iniciamos su suscripción Pro ({PRO_PRICE_LABEL}). Falta un paso:

1. Abra el enlace de PayPal y confirme la suscripción
2. Pro se activa automáticamente en segundos (webhook)
3. Verifique: market whoami  →  tier: pro

CONFIRMAR EN PAYPAL → {approve_url}
{ref_line_es}

Si ya pagó y sigue en tier free, espere 2 minutos y ejecute market doctor.

¿Preguntas? Responda este correo — contestamos el mismo día.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0a0a0b;color:#e5e2e3;padding:24px;">
<h2 style="color:#3afecf;">Confirme Pro en PayPal</h2>
<p>Hola <strong>{username}</strong>,</p>
<p>Pro ({PRO_PRICE_LABEL}) se activa <strong>automáticamente</strong> tras confirmar en PayPal — sin espera manual.</p>
<p><a href="{approve_url}" style="color:#002118;background:#3afecf;padding:12px 24px;text-decoration:none;border-radius:4px;font-weight:bold;">Confirmar en PayPal →</a></p>
<p style="font-size:13px;color:#b9cac2;">Luego: <code>market whoami</code> · <code>market doctor</code></p>
</body></html>"""
    else:
        subject = "Confirm your Pro subscription on PayPal — CLI Market"
        text = f"""Hi {username},

We started your Pro subscription ({PRO_PRICE_LABEL}). One step left:

1. Open the PayPal link and confirm the subscription
2. Pro activates automatically within seconds (webhook)
3. Verify: market whoami  →  tier: pro

CONFIRM ON PAYPAL → {approve_url}
{ref_line_en}

If you already paid and still see free tier, wait 2 minutes and run market doctor.

Questions? Reply to this email — we respond same day.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0a0a0b;color:#e5e2e3;padding:24px;">
<h2 style="color:#3afecf;">Confirm Pro on PayPal</h2>
<p>Hi <strong>{username}</strong>,</p>
<p>Pro ({PRO_PRICE_LABEL}) activates <strong>automatically</strong> after PayPal confirmation — no manual wait.</p>
<p><a href="{approve_url}" style="color:#002118;background:#3afecf;padding:12px 24px;text-decoration:none;border-radius:4px;font-weight:bold;">Confirm on PayPal →</a></p>
<p style="font-size:13px;color:#b9cac2;">Then: <code>market whoami</code> · <code>market doctor</code></p>
</body></html>"""
    return _send(to_email, subject, text, html)


def send_pro_activated_email(
    *,
    to_email: str,
    username: str,
    lang: str = "en",
    subscription_id: str = "",
) -> dict:
    """Confirm Pro activation after PayPal subscription webhook (auto-activate)."""
    sub_line = f"\nSuscripción PayPal: {subscription_id}" if subscription_id else ""
    sub_line_en = f"\nPayPal subscription: {subscription_id}" if subscription_id else ""

    if lang == "es":
        subject = "CLI Market Pro activo — ya puede usar su cuenta"
        text = f"""Hola {username},

Su plan Pro quedó activo. No necesita esperar activación manual.

──────────────────────────────
Siguiente paso en terminal:
  market whoami
  market doctor

Límites Pro:
• 10,000 consultas API / día
• 10 claves API (lectura + escritura)
• Exportación JSON/CSV
• Checkout con PayPal + Yape/Plin
──────────────────────────────
{sub_line}

Docs: https://cli-market.dev/docs#quickstart
Herramientas MCP: https://cli-market.dev/tools

¿Preguntas? Responda este correo — contestamos el mismo día.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0b;font-family:ui-sans-serif,system-ui,sans-serif;color:#e5e2e3;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0b;padding:40px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#131314;border:1px solid #3b4a44;border-radius:12px;max-width:560px;">
<tr><td style="padding:32px 36px;">
<p style="margin:0 0 4px;font-family:monospace;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:#3afecf;">CLI MARKET PRO</p>
<h1 style="margin:0 0 16px;font-size:22px;color:#fff;">Su plan Pro está activo</h1>
<p style="margin:0 0 20px;font-size:14px;color:#b9cac2;line-height:1.6;">
Hola <strong style="color:#fff">{username}</strong>,<br><br>
Confirmamos la activación automática tras su pago en PayPal. Ya puede usar los límites Pro.
</p>
<table width="100%" style="background:#0a0a0b;border:1px solid #3b4a44;border-radius:6px;margin-bottom:20px;">
<tr><td style="padding:14px 18px;font-family:monospace;font-size:12px;color:#b9cac2;line-height:1.8;">
market whoami<br>
market doctor
</td></tr></table>
<p style="margin:0;font-size:13px;color:#b9cac2;">Docs: <a href="https://cli-market.dev/docs#quickstart" style="color:#3afecf;">cli-market.dev/docs</a> · MCP: <a href="https://cli-market.dev/tools" style="color:#3afecf;">cli-market.dev/tools</a></p>
</td></tr>
<tr><td style="padding:20px 36px;border-top:1px solid #3b4a44;">
<p style="margin:0;font-size:12px;color:#b9cac2;">— Ricardo · CLI Market</p>
</td></tr>
</table></td></tr></table>
</body></html>"""
    else:
        subject = "CLI Market Pro is active — your account is ready"
        text = f"""Hi {username},

Your Pro plan is now active. No manual activation wait is required.

──────────────────────────────
Next in your terminal:
  market whoami
  market doctor

Pro limits:
• 10,000 API requests / day
• 10 API keys (read + write)
• JSON/CSV export
• Checkout with PayPal + Yape/Plin
──────────────────────────────
{sub_line_en}

Docs: https://cli-market.dev/docs#quickstart
MCP tools: https://cli-market.dev/tools

Questions? Reply to this email — we respond same day.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0b;font-family:ui-sans-serif,system-ui,sans-serif;color:#e5e2e3;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0b;padding:40px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#131314;border:1px solid #3b4a44;border-radius:12px;max-width:560px;">
<tr><td style="padding:32px 36px;">
<p style="margin:0 0 4px;font-family:monospace;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:#3afecf;">CLI MARKET PRO</p>
<h1 style="margin:0 0 16px;font-size:22px;color:#fff;">Your Pro plan is active</h1>
<p style="margin:0 0 20px;font-size:14px;color:#b9cac2;line-height:1.6;">
Hi <strong style="color:#fff">{username}</strong>,<br><br>
We confirmed automatic activation after your PayPal payment. Pro limits are available now.
</p>
<table width="100%" style="background:#0a0a0b;border:1px solid #3b4a44;border-radius:6px;margin-bottom:20px;">
<tr><td style="padding:14px 18px;font-family:monospace;font-size:12px;color:#b9cac2;line-height:1.8;">
market whoami<br>
market doctor
</td></tr></table>
<p style="margin:0;font-size:13px;color:#b9cac2;">Docs: <a href="https://cli-market.dev/docs#quickstart" style="color:#3afecf;">cli-market.dev/docs</a> · MCP: <a href="https://cli-market.dev/tools" style="color:#3afecf;">cli-market.dev/tools</a></p>
</td></tr>
<tr><td style="padding:20px 36px;border-top:1px solid #3b4a44;">
<p style="margin:0;font-size:12px;color:#b9cac2;">— Ricardo · CLI Market</p>
</td></tr>
</table></td></tr></table>
</body></html>"""
    return _send(to_email, subject, text, html)


def send_starter_subscribe_pending_email(
    *,
    to_email: str,
    username: str,
    approve_url: str,
    request_id: str = "",
    lang: str = "en",
) -> dict:
    """Email after PayPal Starter subscription is created — confirm in PayPal."""
    ref_line_es = f"\nReferencia: {request_id}" if request_id else ""
    ref_line_en = f"\nReference: {request_id}" if request_id else ""

    if lang == "es":
        subject = "Confirme su suscripción Starter en PayPal — CLI Market"
        text = f"""Hola {username},

Iniciamos su suscripción Starter ({STARTER_PRICE_LABEL}). Un paso más:

1. Confirme en PayPal
2. Starter se activa automáticamente en segundos (webhook)
3. Verifique: market whoami  →  tier: starter

CONFIRMAR EN PAYPAL → {approve_url}
{ref_line_es}

Incluye: 5.000 consultas/día · 3 alertas · export CSV.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0a0a0b;color:#e5e2e3;padding:24px;">
<h2 style="color:#3afecf;">Confirme Starter en PayPal</h2>
<p>Hola <strong>{username}</strong>,</p>
<p>Starter ({STARTER_PRICE_LABEL}) se activa <strong>automáticamente</strong> tras confirmar en PayPal.</p>
<p><a href="{approve_url}" style="color:#002118;background:#3afecf;padding:12px 24px;text-decoration:none;border-radius:4px;font-weight:bold;">Confirmar en PayPal →</a></p>
</body></html>"""
    else:
        subject = "Confirm your Starter subscription on PayPal — CLI Market"
        text = f"""Hi {username},

We started your Starter subscription ({STARTER_PRICE_LABEL}). One step left:

1. Confirm on PayPal
2. Starter activates automatically within seconds (webhook)
3. Verify: market whoami  →  tier: starter

CONFIRM ON PAYPAL → {approve_url}
{ref_line_en}

Includes: 5,000 requests/day · 3 alerts · CSV export.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0a0a0b;color:#e5e2e3;padding:24px;">
<h2 style="color:#3afecf;">Confirm Starter on PayPal</h2>
<p>Hi <strong>{username}</strong>,</p>
<p>Starter ({STARTER_PRICE_LABEL}) activates <strong>automatically</strong> after PayPal confirmation.</p>
<p><a href="{approve_url}" style="color:#002118;background:#3afecf;padding:12px 24px;text-decoration:none;border-radius:4px;font-weight:bold;">Confirm on PayPal →</a></p>
</body></html>"""
    return _send(to_email, subject, text, html)


def send_starter_activated_email(
    *,
    to_email: str,
    username: str,
    lang: str = "en",
    subscription_id: str = "",
) -> dict:
    """Confirm Starter activation after PayPal webhook."""
    sub_line_es = f"\nSuscripción PayPal: {subscription_id}" if subscription_id else ""
    sub_line_en = f"\nPayPal subscription: {subscription_id}" if subscription_id else ""

    if lang == "es":
        subject = "CLI Market Starter activo — alertas y export listos"
        text = f"""Hola {username},

Su plan Starter quedó activo. No necesita activación manual.

──────────────────────────────
Siguiente paso en terminal:
  market whoami
  market doctor
  market alerts --action list

Límites Starter:
• 5.000 consultas / día
• 3 claves API (lectura)
• 3 alertas de precio
• Exportación CSV
──────────────────────────────
{sub_line_es}

Docs: https://cli-market.dev/docs#quickstart
Herramientas MCP: https://cli-market.dev/tools

¿Preguntas? Responda este correo — contestamos el mismo día.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0b;font-family:ui-sans-serif,system-ui,sans-serif;color:#e5e2e3;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0b;padding:40px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#131314;border:1px solid #3b4a44;border-radius:12px;max-width:560px;">
<tr><td style="padding:32px 36px;">
<p style="margin:0 0 4px;font-family:monospace;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:#3afecf;">CLI MARKET STARTER</p>
<h1 style="margin:0 0 16px;font-size:22px;color:#fff;">Su plan Starter está activo</h1>
<p style="margin:0 0 20px;font-size:14px;color:#b9cac2;line-height:1.6;">
Hola <strong style="color:#fff">{username}</strong>,<br><br>
Confirmamos la activación automática tras su pago en PayPal. Ya puede usar alertas y exportación CSV.
</p>
<table width="100%" style="background:#0a0a0b;border:1px solid #3b4a44;border-radius:6px;margin-bottom:20px;">
<tr><td style="padding:14px 18px;font-family:monospace;font-size:12px;color:#b9cac2;line-height:1.8;">
market whoami<br>
market doctor<br>
market alerts --action list
</td></tr></table>
<p style="margin:0;font-size:13px;color:#b9cac2;">Docs: <a href="https://cli-market.dev/docs#quickstart" style="color:#3afecf;">cli-market.dev/docs</a> · MCP: <a href="https://cli-market.dev/tools" style="color:#3afecf;">cli-market.dev/tools</a></p>
</td></tr>
<tr><td style="padding:20px 36px;border-top:1px solid #3b4a44;">
<p style="margin:0;font-size:12px;color:#b9cac2;">— Ricardo · CLI Market</p>
</td></tr>
</table></td></tr></table>
</body></html>"""
    else:
        subject = "CLI Market Starter is active — alerts and export ready"
        text = f"""Hi {username},

Your Starter plan is now active. No manual activation wait is required.

──────────────────────────────
Next in your terminal:
  market whoami
  market doctor
  market alerts --action list

Starter limits:
• 5,000 requests / day
• 3 API keys (read-only)
• 3 price alerts
• CSV export
──────────────────────────────
{sub_line_en}

Docs: https://cli-market.dev/docs#quickstart
MCP tools: https://cli-market.dev/tools

Questions? Reply to this email — we respond same day.

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0b;font-family:ui-sans-serif,system-ui,sans-serif;color:#e5e2e3;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0b;padding:40px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#131314;border:1px solid #3b4a44;border-radius:12px;max-width:560px;">
<tr><td style="padding:32px 36px;">
<p style="margin:0 0 4px;font-family:monospace;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:#3afecf;">CLI MARKET STARTER</p>
<h1 style="margin:0 0 16px;font-size:22px;color:#fff;">Your Starter plan is active</h1>
<p style="margin:0 0 20px;font-size:14px;color:#b9cac2;line-height:1.6;">
Hi <strong style="color:#fff">{username}</strong>,<br><br>
We confirmed automatic activation after your PayPal payment. Alerts and CSV export are available now.
</p>
<table width="100%" style="background:#0a0a0b;border:1px solid #3b4a44;border-radius:6px;margin-bottom:20px;">
<tr><td style="padding:14px 18px;font-family:monospace;font-size:12px;color:#b9cac2;line-height:1.8;">
market whoami<br>
market doctor<br>
market alerts --action list
</td></tr></table>
<p style="margin:0;font-size:13px;color:#b9cac2;">Docs: <a href="https://cli-market.dev/docs#quickstart" style="color:#3afecf;">cli-market.dev/docs</a> · MCP: <a href="https://cli-market.dev/tools" style="color:#3afecf;">cli-market.dev/tools</a></p>
</td></tr>
<tr><td style="padding:20px 36px;border-top:1px solid #3b4a44;">
<p style="margin:0;font-size:12px;color:#b9cac2;">— Ricardo · CLI Market</p>
</td></tr>
</table></td></tr></table>
</body></html>"""
    return _send(to_email, subject, text, html)


def send_starter_request_received_email(
    *,
    to_email: str,
    request_id: str,
    lang: str = "en",
    name: str = "",
) -> dict:
    """Acknowledge Starter access request — manual activation, no instant checkout."""
    greet = name or to_email.split("@")[0]
    if lang == "es":
        subject = f"Solicitud Starter recibida — {request_id}"
        text = f"""Hola {greet},

Recibimos su solicitud de plan Starter ({request_id}).

──────────────────────────────
Qué sigue
• Activación manual en ≤24 horas hábiles
• Le enviaremos email cuando su tier sea Starter
• Mientras tanto puede usar Free: market register + market whoami
──────────────────────────────

Starter incluye:
• 5,000 consultas / día
• 3 claves API (lectura)
• 3 alertas de precio
• Exportación CSV

Docs: https://cli-market.dev/docs#quickstart

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0a0a0b;color:#e5e2e3;padding:24px;">
<h2 style="color:#3afecf;">Solicitud Starter recibida</h2>
<p>Hola {greet},</p>
<p>Referencia: <code style="color:#3afecf;">{request_id}</code></p>
<p>Activación manual en <strong>≤24h hábiles</strong>. No hay checkout instantáneo en este plan.</p>
<p>Mientras tanto: <code>market register</code> → <code>market whoami</code></p>
</body></html>"""
    else:
        subject = f"Starter request received — {request_id}"
        text = f"""Hi {greet},

We received your Starter plan request ({request_id}).

──────────────────────────────
What's next
• Manual activation within 24 business hours
• We'll email you when your tier is Starter
• Meanwhile use Free: market register + market whoami
──────────────────────────────

Starter includes:
• 5,000 requests / day
• 3 API keys (read-only)
• 3 price alerts
• CSV export

Docs: https://cli-market.dev/docs#quickstart

— Ricardo · CLI Market
hello@cli-market.dev
"""
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0a0a0b;color:#e5e2e3;padding:24px;">
<h2 style="color:#3afecf;">Starter request received</h2>
<p>Hi {greet},</p>
<p>Reference: <code style="color:#3afecf;">{request_id}</code></p>
<p>Manual activation within <strong>24 business hours</strong>. No instant checkout on this plan.</p>
<p>Meanwhile: <code>market register</code> → <code>market whoami</code></p>
</body></html>"""
    return _send(to_email, subject, text, html)


def send_starter_request_notify(
    *,
    subscriber_email: str,
    request_id: str,
    profile: str = "",
    name: str = "",
    note: str = "",
) -> dict:
    """Notify hello@cli-market.dev of a new Starter request."""
    subject = f"[Starter request] {request_id} — {subscriber_email}"
    text = (
        f"New Starter access request\n\n"
        f"Request ID: {request_id}\n"
        f"Email: {subscriber_email}\n"
    )
    if name:
        text += f"Name: {name}\n"
    if profile:
        text += f"Profile: {profile}\n"
    if note.strip():
        text += f"\nNote:\n{note.strip()}\n"
    text += (
        f"\nActivate manually (ops/activate_starter.py or dashboard) within 24h.\n"
    )
    return _send(NOTIFY_EMAIL, subject, text, f"<pre>{text}</pre>")


def send_pro_request_notify(
    *,
    subscriber_email: str,
    username: str,
    request_id: str,
    note: str = "",
) -> dict:
    """Notify hello@cli-market.dev of a new Pro request."""
    subject = f"[Pro request] {username} — {request_id}"
    text = (
        f"New Pro subscription request\n\n"
        f"Request ID: {request_id}\n"
        f"Username: {username}\n"
        f"Email: {subscriber_email}\n"
        f"Payment link sent: {PRO_PAYMENT_URL}\n"
    )
    if note.strip():
        text += f"\nUse case / note:\n{note.strip()}\n"
    text += (
        f"\nAfter payment confirmed, run:\n"
        f"  python3 ops/activate_pro.py {username}\n"
    )
    return _send(NOTIFY_EMAIL, subject, text, f"<pre>{text}</pre>")


def send_contact_notify(
    *,
    email: str,
    plan: str,
    profile: str = "",
    name: str = "",
    company: str = "",
    use_case: str = "",
) -> dict:
    """Notify hello@cli-market.dev of a new contact form submission."""
    label = f"[{plan}/{profile}]" if profile else f"[{plan}]"
    subject = f"{label} {name or email}"
    text = f"New contact submission\n\nPlan: {plan}\nEmail: {email}\n"
    if profile:
        text += f"Profile: {profile}\n"
    if name:
        text += f"Name: {name}\n"
    if company:
        text += f"Company: {company}\n"
    if use_case.strip():
        text += f"\nMessage:\n{use_case.strip()}\n"
    return _send(NOTIFY_EMAIL, subject, text, f"<pre>{text}</pre>")


def _send(to_email: str, subject: str, text: str, html: str) -> dict:
    if not _smtp_configured():
        logger.warning("SMTP not configured — email not sent to %s", to_email)
        return {"sent": False, "reason": "smtp_not_configured", "to": to_email}

    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Reply-To"] = FROM_EMAIL
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    timeout = int(os.getenv("SMTP_TIMEOUT", "5"))
    try:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            if use_tls:
                smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(FROM_EMAIL, [to_email], msg.as_string())
        return {"sent": True, "to": to_email}
    except Exception as e:
        logger.exception("Failed to send email to %s", to_email)
        return {"sent": False, "reason": str(e), "to": to_email}
