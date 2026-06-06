"""market_connectors — Multi-platform e-commerce connectors."""
from .vtex import VtexConnector
from .shopify import ShopifyConnector
from .magento import MagentoConnector
from .woocommerce import WooCommerceConnector

_CONNECTORS = {
    "vtex": VtexConnector(),
    "shopify": ShopifyConnector(),
    "magento": MagentoConnector(),
    "woocommerce": WooCommerceConnector(),
}

def get_connector(platform: str):
    conn = _CONNECTORS.get(platform)
    if not conn:
        raise ValueError(f"Unknown platform: {platform}. Known: {list(_CONNECTORS)}")
    return conn
