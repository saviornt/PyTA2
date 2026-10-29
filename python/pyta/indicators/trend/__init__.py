"""Trend indicators, one module per indicator.

Available: ADX, DEMA, EMA, KAMA, MACD, Parabolic SAR, SMA, TEMA, WMA.
Planned: Ichimoku Cloud, Aroon (see the README catalog).
"""

from pyta.indicators.trend.adx import adx
from pyta.indicators.trend.dema import dema
from pyta.indicators.trend.ema import ema
from pyta.indicators.trend.kama import kama
from pyta.indicators.trend.macd import macd
from pyta.indicators.trend.sar import sar
from pyta.indicators.trend.sma import sma
from pyta.indicators.trend.tema import tema
from pyta.indicators.trend.wma import wma

__all__ = ["adx", "dema", "ema", "kama", "macd", "sar", "sma", "tema", "wma"]
