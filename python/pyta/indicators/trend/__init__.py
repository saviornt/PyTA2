"""Trend indicators, one module per indicator.

Available: DEMA, EMA, KAMA, MACD, SMA, TEMA, WMA. Planned: ADX, Parabolic
SAR, Ichimoku Cloud, Aroon (see the README catalog).
"""

from pyta.indicators.trend.dema import dema
from pyta.indicators.trend.ema import ema
from pyta.indicators.trend.kama import kama
from pyta.indicators.trend.macd import macd
from pyta.indicators.trend.sma import sma
from pyta.indicators.trend.tema import tema
from pyta.indicators.trend.wma import wma

__all__ = ["dema", "ema", "kama", "macd", "sma", "tema", "wma"]
