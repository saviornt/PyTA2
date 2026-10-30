"""PyTA: Rust-powered technical analysis indicators.

Call an indicator by short-hand name (`pyta.sma`) or by category (`pyta.trend.sma`);
both are the same function. `pyta.batch` mirrors both styles.
"""

import logging

from . import batch, indicators, momentum, trend, volatility, volume
from ._export import Output
from .indicators import (
    ad,
    adx,
    aroon,
    atr,
    bbands,
    cci,
    cmf,
    dema,
    donchian,
    ema,
    ichimoku,
    kama,
    keltner,
    macd,
    mfi,
    obv,
    roc,
    rsi,
    sar,
    sma,
    stddev,
    stoch,
    tema,
    trix,
    ultosc,
    vwap,
    willr,
    wma,
)

# A library adds only a NullHandler and never sets levels; the application
# configures logging. Rust records arrive through the same "pyta.*" loggers.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "Output",
    "ad",
    "adx",
    "aroon",
    "atr",
    "batch",
    "bbands",
    "cci",
    "cmf",
    "dema",
    "donchian",
    "ema",
    "ichimoku",
    "indicators",
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
    "vwap",
    "willr",
    "wma",
]
