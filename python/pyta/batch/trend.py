"""Trend batch namespace: `pyta.batch.trend.<indicator>`."""

from pyta.indicators.trend.adx import adx_batch as adx
from pyta.indicators.trend.dema import dema_batch as dema
from pyta.indicators.trend.ema import ema_batch as ema
from pyta.indicators.trend.kama import kama_batch as kama
from pyta.indicators.trend.macd import macd_batch as macd
from pyta.indicators.trend.sma import sma_batch as sma
from pyta.indicators.trend.tema import tema_batch as tema
from pyta.indicators.trend.wma import wma_batch as wma

__all__ = ["adx", "dema", "ema", "kama", "macd", "sma", "tema", "wma"]
