"""Trend indicators, one module per indicator.

Available: EMA, MACD, SMA, WMA. Planned: DEMA, TEMA, KAMA, ADX, Parabolic SAR,
Ichimoku Cloud, Aroon (see the README catalog).
"""

from pyta.indicators.trend.ema import ema
from pyta.indicators.trend.macd import macd
from pyta.indicators.trend.sma import sma
from pyta.indicators.trend.wma import wma

__all__ = ["ema", "macd", "sma", "wma"]
