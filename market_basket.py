"""Compatibility shim — prefer ``market_core.market_basket`` in new code."""

from market_core.market_basket import *  # noqa: F403
from market_core.market_basket import _canasta_name_sql  # noqa: F401 — backend tests
