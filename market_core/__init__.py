"""CLI Market core package — re-exports the public API from ``market_core.market_core``."""

from .market_core import *  # noqa: F403
from .market_core import _db_initialized  # noqa: F401 — tests reset DB init state