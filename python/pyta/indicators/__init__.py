"""Indicator functions in category subpackages, one module per indicator.

`pyta.indicators.<category>.<name>` is the module path; every indicator function
is also re-exported here and at the top level, so `pyta.indicators.sma`,
`pyta.trend.sma` and `pyta.sma` are the same function.
"""

from pyta.indicators import momentum, trend
from pyta.indicators.momentum import cci, rsi
from pyta.indicators.trend import sma

__all__ = ["cci", "momentum", "rsi", "sma", "trend"]
