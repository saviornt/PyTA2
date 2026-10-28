"""PyTA: Rust-powered technical analysis indicators."""

import logging

from . import batch, indicators
from .indicators import rsi, sma

# A library adds only a NullHandler and never sets levels; the application
# configures logging. Rust records arrive through the same "pyta.*" loggers.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["batch", "indicators", "rsi", "sma"]
