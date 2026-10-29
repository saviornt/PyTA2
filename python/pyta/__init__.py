"""PyTA: Rust-powered technical analysis indicators.

Call an indicator by short-hand name (`pyta.sma`) or by category (`pyta.trend.sma`);
both are the same function. `pyta.batch` mirrors both styles.
"""

import logging

from . import batch, indicators, momentum, trend, volatility, volume
from ._export import Output
from .indicators import atr, bbands, cci, dema, donchian, ema, keltner, macd, rsi, sma, stddev, wma

# A library adds only a NullHandler and never sets levels; the application
# configures logging. Rust records arrive through the same "pyta.*" loggers.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "Output",
    "atr",
    "batch",
    "bbands",
    "cci",
    "dema",
    "donchian",
    "ema",
    "indicators",
    "keltner",
    "macd",
    "momentum",
    "rsi",
    "sma",
    "stddev",
    "trend",
    "volatility",
    "volume",
    "wma",
]
