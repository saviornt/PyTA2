"""Trend indicators, one module per indicator.

Available: EMA, MACD, SMA. Planned: WMA, DEMA, TEMA, KAMA, ADX, Parabolic SAR,
Ichimoku Cloud, Aroon (see the README catalog).
"""

from pyta.indicators.trend.ema import ema
from pyta.indicators.trend.macd import macd
from pyta.indicators.trend.sma import sma

__all__ = ["ema", "macd", "sma"]
