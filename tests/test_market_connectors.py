"""Tests for market connectors."""
import pytest


class TestBaseConnector:
    """Test base connector functionality."""

    def test_import(self):
        """Verify module can be imported."""
        from market_connectors import base
        assert hasattr(base, "__file__")


class TestShopify:
    """Test Shopify connector."""

    def test_import(self):
        """Verify module can be imported."""
        from market_connectors import shopify
        assert hasattr(shopify, "__file__")


class TestVTEX:
    """Test VTEX connector."""

    def test_import(self):
        """Verify module can be imported."""
        from market_connectors import vtex
        assert hasattr(vtex, "__file__")


class TestPayPal:
    """Test PayPal connector."""

    def test_import(self):
        """Verify module can be imported."""
        from market_connectors import paypal_payments
        assert hasattr(paypal_payments, "__file__")


class TestWise:
    """Test Wise connector."""

    def test_import(self):
        """Verify module can be imported."""
        from market_connectors import wise_payments
        assert hasattr(wise_payments, "__file__")


class TestSunat:
    """Test SUNAT connector."""

    def test_import(self):
        """Verify module can be imported."""
        from market_connectors import sunat_invoicing
        assert hasattr(sunat_invoicing, "__file__")

    def test_railway_env_aliases(self, monkeypatch):
        from market_connectors import sunat_invoicing as sunat

        monkeypatch.delenv("SUNAT_RUC", raising=False)
        monkeypatch.delenv("SUNAT_SOL_USER", raising=False)
        monkeypatch.delenv("SUNAT_SOL_PASS", raising=False)
        monkeypatch.setenv("SINAPSIS_RUC", "20123456789")
        monkeypatch.setenv("CLAVE_SOL_TOKEN", "MODDATOS")
        monkeypatch.setenv("PASSWORD_SUNAT_SINAPSIS", "secret-pass")

        assert sunat.get_sunat_ruc() == "20123456789"
        assert sunat.get_sol_user() == "MODDATOS"
        assert sunat.get_sol_password() == "secret-pass"
        assert sunat.sol_credentials_configured() is True
        assert sunat.get_company()["ruc"] == "20123456789"
        assert sunat._sol_username() == "20123456789MODDATOS"

    def test_sol_username_already_prefixed(self, monkeypatch):
        from market_connectors import sunat_invoicing as sunat

        monkeypatch.setenv("SUNAT_RUC", "20123456789")
        monkeypatch.setenv("SUNAT_SOL_USER", "20123456789MODDATOS")
        monkeypatch.setenv("SUNAT_SOL_PASS", "x")
        assert sunat._sol_username() == "20123456789MODDATOS"

    def test_pse_railway_aliases(self, monkeypatch):
        from market_connectors import sunat_invoicing as sunat

        monkeypatch.delenv("SUNAT_PSE_API_URL", raising=False)
        monkeypatch.setenv("PSE_SUNAT_ID", "03989d1a-6c8c-4b71-b1cd-7d37001deaa0")
        monkeypatch.setenv("PSE_SUNAT_PASSWORD", "my-token-secret")
        monkeypatch.setenv("SUNAT_PSE_PROVIDER", "nubefact")
        monkeypatch.setenv("SUNAT_MODE", "demo")

        assert sunat.get_pse_token() == "my-token-secret"
        assert sunat.pse_credentials_configured() is True
        assert sunat.get_pse_api_url().endswith("03989d1a-6c8c-4b71-b1cd-7d37001deaa0")
        assert "api.nubefact.com" in sunat.get_pse_api_url()
