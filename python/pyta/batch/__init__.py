"""Batch namespace: `pyta.batch.<indicator>` runs one indicator over many datasets.

Each name is the batch function defined next to its single-call counterpart in
`pyta.indicators.<category>.<indicator>`, and is also reachable by category as
`pyta.batch.<category>.<indicator>`. A dataset that fails is returned as its
exception in place, so one bad dataset never prevents results for the others.
"""

from pyta.batch import momentum, trend, volatility, volume
from pyta.batch.momentum import cci, mfi, roc, rsi, stoch, trix, ultosc, willr
from pyta.batch.trend import adx, aroon, dema, ema, ichimoku, kama, macd, sar, sma, tema, wma
from pyta.batch.volatility import atr, bbands, donchian, keltner, stddev
from pyta.batch.volume import ad, cmf, obv, vroc, vwap

__all__ = [
    "ad",
    "adx",
    "aroon",
    "atr",
    "bbands",
    "cci",
    "cmf",
    "dema",
    "donchian",
    "ema",
    "ichimoku",
    "kama",
    "keltner",
    "macd",
    "mfi",
    "momentum",
    "obv",
    "roc",
    "rsi",
    "sar",
    "sma",
    "stddev",
    "stoch",
    "tema",
    "trend",
    "trix",
    "ultosc",
    "volatility",
    "volume",
    "vroc",
    "vwap",
    "willr",
    "wma",
]
