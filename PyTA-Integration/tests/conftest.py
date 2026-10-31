"""Shared fixtures."""

import pandas as pd
import pytest
from yfinance_dataframe import load_yfinance_frame


@pytest.fixture
def spy() -> pd.DataFrame:
    """300 SPY sessions shaped like yfinance's `history(auto_adjust=False)`."""
    return load_yfinance_frame()
