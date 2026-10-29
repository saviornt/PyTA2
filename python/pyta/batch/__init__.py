"""Batch namespace: `pyta.batch.<indicator>` runs one indicator over many datasets.

Each name is the batch function defined next to its single-call counterpart in
`pyta.indicators.<category>.<indicator>`, and is also reachable by category as
`pyta.batch.<category>.<indicator>`. A dataset that fails is returned as its
exception in place, so one bad dataset never prevents results for the others.
"""

from pyta.batch import momentum, trend, volatility, volume
from pyta.batch.momentum import cci, rsi, stoch
from pyta.batch.trend import adx, aroon, dema, ema, ichimoku, kama, macd, sar, sma, tema, wma
from pyta.batch.volatility import atr, bbands, donchian, keltner, stddev

__all__ = [
    "adx",
    "aroon",
    "atr",
    "bbands",
    "cci",
    "dema",
    "donchian",
    "ema",
    "ichimoku",
    "kama",
    "keltner",
    "macd",
    "momentum",
    "rsi",
    "sar",
    "sma",
    "stddev",
    "stoch",
    "tema",
    "trend",
    "volatility",
    "volume",
    "wma",
]
