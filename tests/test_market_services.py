"""Tests for market service modules."""
import pytest


class TestMarketCore:
    """Test market_core.py orchestrator."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import market_core
        assert hasattr(market_core, "__file__")


class TestMarketDB:
    """Test market_db.py database layer."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import market_db
        assert hasattr(market_db, "__file__")


class TestMarketMCP:
    """Test market_mcp.py MCP tools."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import market_mcp
        assert hasattr(market_mcp, "__file__")


class TestMarketIntelAgent:
    """Test market_intel_agent.py AI agent."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import market_intel_agent
        assert hasattr(market_intel_agent, "__file__")


class TestMarketEnrichSources:
    """Test market_enrich_sources.py external data."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import market_enrich_sources
        assert hasattr(market_enrich_sources, "__file__")


class TestMarketEnrichSubcategory:
    """Test market_enrich_subcategory.py classification."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import market_enrich_subcategory
        assert hasattr(market_enrich_subcategory, "__file__")


class TestMarketHealthAlert:
    """Test market_health_alert.py monitoring."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import market_health_alert
        assert hasattr(market_health_alert, "__file__")


class TestSourceHealth:
    """Test source_health.py scraper health."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import source_health
        assert hasattr(source_health, "__file__")


class TestStoreCredentials:
    """Test store_credentials.py credential management."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import store_credentials
        assert hasattr(store_credentials, "__file__")


class TestRetailerOnboarding:
    """Test retailer_onboarding.py workflow."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import retailer_onboarding
        assert hasattr(retailer_onboarding, "__file__")


class TestDataV1Service:
    """Test data_v1_service.py API endpoints."""

    def test_import(self):
        """Verify module can be imported."""
        from market_core import data_v1_service
        assert hasattr(data_v1_service, "__file__")
