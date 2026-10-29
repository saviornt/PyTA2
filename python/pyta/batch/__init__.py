"""Batch namespace: `pyta.batch.<indicator>` runs one indicator over many datasets.

Each name is the batch function defined next to its single-call counterpart in
`pyta.indicators.<category>.<indicator>`, and is also reachable by category as
`pyta.batch.<category>.<indicator>`. A dataset that fails is returned as its
exception in place, so one bad dataset never prevents results for the others.
"""

from pyta.batch import momentum, trend, volatility, volume
from pyta.batch.momentum import cci, rsi
from pyta.batch.trend import dema, ema, macd, sma, tema, wma
from pyta.batch.volatility import atr, bbands, donchian, keltner, stddev

__all__ = [
    "atr",
    "bbands",
    "cci",
    "dema",
    "donchian",
    "ema",
    "keltner",
    "macd",
    "momentum",
    "rsi",
    "sma",
    "stddev",
    "tema",
    "trend",
    "volatility",
    "volume",
    "wma",
]
