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
PRO_PRICE_LABEL = os.getenv("PRO_PRICE_LABEL", "$49/month")


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

Activamos tu cuenta Pro en menos de 24 h y te confirmamos por email.

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
          Activamos tu cuenta en <strong style="color:#fff">menos de 24 h</strong> y te confirmamos por email.<br>
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

We activate your Pro account within 24 hours and confirm by email.

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
