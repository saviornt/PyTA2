"""Trend batch namespace: `pyta.batch.trend.<indicator>`."""

from pyta.indicators.trend.ema import ema_batch as ema
from pyta.indicators.trend.macd import macd_batch as macd
from pyta.indicators.trend.sma import sma_batch as sma

__all__ = ["ema", "macd", "sma"]
