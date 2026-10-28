"""Trend indicators, one module per indicator.

Available: SMA. Planned: EMA, WMA, DEMA, TEMA, KAMA, MACD, ADX, Parabolic SAR,
Ichimoku Cloud, Aroon (see the README catalog).
"""

from pyta.indicators.trend.sma import sma

__all__ = ["sma"]
