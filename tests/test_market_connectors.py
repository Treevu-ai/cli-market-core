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
