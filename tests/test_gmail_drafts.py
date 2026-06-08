"""Tests for Gmail draft integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestGmailDrafts:
    def test_gmail_drafts_enabled_with_workspace_smtp(self, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "hello@cli-market.dev")
        monkeypatch.setenv("SMTP_PASSWORD", "app-pass")
        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
        from market_connectors.gmail_drafts import gmail_drafts_enabled

        assert gmail_drafts_enabled() is True

    def test_gmail_drafts_disabled_by_flag(self, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "hello@cli-market.dev")
        monkeypatch.setenv("SMTP_PASSWORD", "app-pass")
        monkeypatch.setenv("GMAIL_DRAFTS_ENABLED", "false")
        from market_connectors.gmail_drafts import gmail_drafts_enabled

        assert gmail_drafts_enabled() is False

    @patch("market_connectors.gmail_drafts.imaplib.IMAP4_SSL")
    def test_create_gmail_draft_appends_to_drafts(self, mock_imap_cls, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "hello@cli-market.dev")
        monkeypatch.setenv("SMTP_PASSWORD", "app-pass")
        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")

        mock_imap = MagicMock()
        mock_imap.list.return_value = (
            "OK",
            [b'(\\Drafts \\HasNoChildren) "/" "[Gmail]/Borradores"'],
        )
        mock_imap.append.return_value = ("OK", [b"APPENDUID 1 42"])
        mock_imap_cls.return_value = mock_imap

        from market_connectors.gmail_drafts import create_gmail_draft

        result = create_gmail_draft(
            to_email="client@example.com",
            subject="RE: CLI Market Pro",
            body_text="Hola,\n\nPro activo.\n",
        )

        assert result["created"] is True
        assert result["to"] == "client@example.com"
        assert result["draft_uid"] == "42"
        mock_imap.login.assert_called_once_with("hello@cli-market.dev", "app-pass")
        mock_imap.append.assert_called_once()
        args = mock_imap.append.call_args[0]
        assert args[0] == "[Gmail]/Borradores"
        assert args[1] == "\\Draft"


class TestProActivationEmail:
    def test_quickstart_includes_username_and_login(self):
        from market_connectors.email_outbound import (
            _pro_activation_quickstart_text,
            format_pro_activated_reply_draft,
        )

        from market_connectors.email_outbound import compose_pro_welcome_email

        composed = compose_pro_welcome_email(
            display_name="Ricardo",
            username="acubatruweb",
            email="acubatruweb@outlook.com",
            password="Secr3t-Cli9",
            lang="es",
            payment_method="yape",
            request_id="PRO-3E2A9E04",
        )
        assert "Hola Ricardo" in composed["text"]
        assert "Email · acubatruweb@outlook.com" in composed["text"]
        assert "Usuario CLI · acubatruweb" in composed["text"]
        assert "Contraseña · Secr3t-Cli9" in composed["text"]
        assert "```bash" in composed["text"]
        assert "market login --username acubatruweb --password Secr3t-Cli9" in composed["text"]
        assert "no reinstales" in composed["text"]

        draft = format_pro_activated_reply_draft(
            username="acubatruweb",
            lang="es",
            payment_method="yape",
            request_id="PRO-3E2A9E04",
            password="Secr3t-Cli9",
            email="acubatruweb@outlook.com",
            display_name="Ricardo",
        )
        assert "Ricardo" in draft["subject"]
        assert "Hola Ricardo" in draft["text"]
        assert "PRO-3E2A9E04" in draft["text"]