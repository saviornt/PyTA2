"""Shared pytest fixtures."""

import pytest
from ohlcv_data import Ohlcv, load


@pytest.fixture(scope="session")
def ohlcv() -> Ohlcv:
    """300 sessions of real daily SPY OHLCV (read-only arrays)."""
    return load()
