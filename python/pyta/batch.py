"""Batch namespace: `pyta.batch.<indicator>` runs one indicator over many datasets.

Each name is the batch function defined next to its single-call counterpart in
`pyta.indicators.<indicator>`. A dataset that fails is returned as its exception
in place, so one bad dataset never prevents results for the others.
"""

from .indicators.rsi import rsi_batch as rsi
from .indicators.sma import sma_batch as sma

__all__ = ["rsi", "sma"]
