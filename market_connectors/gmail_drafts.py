"""Create reply drafts in Gmail via IMAP (reuses SMTP app-password credentials)."""

from __future__ import annotations

import imaplib
import logging
import os
import time
from email.message import EmailMessage
from email.utils import formataddr

logger = logging.getLogger(__name__)

DEFAULT_IMAP_HOST = "imap.gmail.com"
DEFAULT_IMAP_PORT = 993
DRAFTS_FOLDER = "[Gmail]/Drafts"
DRAFTS_FOLDER_CANDIDATES = (
    "[Gmail]/Drafts",
    "[Gmail]/Borradores",
    "Drafts",
    "Borradores",
)


def _imap_credentials() -> tuple[str, str] | None:
    user = (os.getenv("SMTP_USER") or os.getenv("GMAIL_IMAP_USER") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_IMAP_PASSWORD") or "").strip()
    if user and password:
        return user, password
    return None


def gmail_drafts_enabled() -> bool:
    if os.getenv("GMAIL_DRAFTS_ENABLED", "true").lower() in ("0", "false", "no"):
        return False
    if not _imap_credentials():
        return False
    if os.getenv("GMAIL_IMAP_HOST"):
        return True
    host = (os.getenv("SMTP_HOST") or "").lower()
    user = (os.getenv("SMTP_USER") or "").lower()
    if "gmail" in host:
        return True
    if user.endswith("@gmail.com") or user.endswith("@cli-market.dev"):
        return True
    return False


def _resolve_drafts_folder(imap: imaplib.IMAP4_SSL, configured: str) -> str:
    if configured and configured not in DRAFTS_FOLDER_CANDIDATES:
        return configured

    status, boxes = imap.list()
    if status == "OK" and boxes:
        for raw in boxes:
            line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            if "\\Drafts" not in line:
                continue
            # LIST line ends with quoted mailbox name, e.g. "/" "[Gmail]/Borradores"
            if '"' in line:
                name = line.rsplit('"', 2)[-2]
                if name:
                    return name

    for candidate in DRAFTS_FOLDER_CANDIDATES:
        status, _ = imap.select(candidate, readonly=True)
        if status == "OK":
            imap.close()
            return candidate

    return configured or DRAFTS_FOLDER


def create_gmail_draft(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    from_email: str | None = None,
    from_name: str | None = None,
) -> dict:
    """Append a draft to Gmail Drafts (hello@cli-market.dev inbox)."""
    if not gmail_drafts_enabled():
        return {"created": False, "reason": "gmail_drafts_disabled"}

    creds = _imap_credentials()
    if not creds:
        return {"created": False, "reason": "imap_not_configured"}

    imap_user, imap_password = creds
    imap_host = os.getenv("GMAIL_IMAP_HOST", DEFAULT_IMAP_HOST)
    imap_port = int(os.getenv("GMAIL_IMAP_PORT", str(DEFAULT_IMAP_PORT)))
    sender = (from_email or os.getenv("BILLING_FROM_EMAIL") or imap_user).strip()
    display_name = (from_name or os.getenv("BILLING_FROM_NAME") or "CLI Market").strip()
    drafts_folder_cfg = os.getenv("GMAIL_DRAFTS_FOLDER", "").strip()
    timeout = int(os.getenv("GMAIL_IMAP_TIMEOUT", "15"))

    msg = EmailMessage()
    msg["From"] = formataddr((display_name, sender))
    msg["To"] = to_email.strip()
    msg["Subject"] = subject
    msg["Reply-To"] = sender
    msg.set_content(body_text, charset="utf-8")

    imap: imaplib.IMAP4_SSL | None = None
    try:
        imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=timeout)
        imap.login(imap_user, imap_password)
        drafts_folder = _resolve_drafts_folder(imap, drafts_folder_cfg)
        internal_date = imaplib.Time2Internaldate(time.time())
        status, data = imap.append(
            drafts_folder,
            "\\Draft",
            internal_date,
            msg.as_bytes(),
        )
        if status != "OK":
            return {
                "created": False,
                "reason": f"imap_append_failed:{status}",
                "folder": drafts_folder,
            }
        draft_uid = None
        if data and data[0]:
            raw = data[0]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            if "APPENDUID" in raw:
                parts = raw.split()
                if parts:
                    draft_uid = parts[-1]
        return {
            "created": True,
            "to": to_email,
            "subject": subject,
            "folder": drafts_folder,
            "draft_uid": draft_uid,
        }
    except Exception as exc:
        logger.exception("Gmail draft creation failed for %s", to_email)
        return {"created": False, "reason": str(exc), "to": to_email}
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:
                pass