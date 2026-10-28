"""PyTA: Rust-powered technical analysis indicators.

Call an indicator by short-hand name (`pyta.sma`) or by category (`pyta.trend.sma`);
both are the same function. `pyta.batch` mirrors both styles.
"""

import logging

from . import batch, indicators, momentum, trend
from .indicators import cci, rsi, sma

# A library adds only a NullHandler and never sets levels; the application
# configures logging. Rust records arrive through the same "pyta.*" loggers.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["batch", "cci", "indicators", "momentum", "rsi", "sma", "trend"]
