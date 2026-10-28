"""Batch namespace: `pyta.batch.<indicator>` runs one indicator over many datasets.

Each name is the batch function defined next to its single-call counterpart in
`pyta.indicators.<category>.<indicator>`, and is also reachable by category as
`pyta.batch.<category>.<indicator>`. A dataset that fails is returned as its
exception in place, so one bad dataset never prevents results for the others.
"""

from pyta.batch import momentum, trend
from pyta.batch.momentum import cci, rsi
from pyta.batch.trend import sma

__all__ = ["cci", "momentum", "rsi", "sma", "trend"]
