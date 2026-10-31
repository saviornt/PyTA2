"""Expected values on the SPY sample, checked against numbers computed without PyTA.

The literal reference numbers were computed once from `data/spy_daily.csv` with the standard
library only (`math.fsum` window sums, Wilder's RSI loop, TA-Lib-seeded EMAs for MACD), not read
from PyTA's own tests; the tests below also recompute SMA, RSI and OBV with plain pandas/NumPy.
"""

import json
import math

import numpy as np
import pandas as pd
import pyta
import pytest

TOLERANCE = 1e-9  # PyTA's documented agreement with TA-Lib-style references

# Last three values of each indicator on the 300 SPY sessions (2025-12-29 to 2025-12-31).
SMA_20 = [683.5165, 683.8535, 683.873]
RSI_14 = [57.45037179535845, 56.38515548974688, 50.29919440339596]
# Last row of MACD(12, 26, 9).
MACD_LAST = (2.693378202115241, 2.748232567965818, -0.054854365850577125)
OBV_LAST = 1255323500.0


def wilder_rsi(close: np.ndarray, period: int) -> np.ndarray:
    changes = np.diff(close)
    gains, losses = np.clip(changes, 0, None), np.clip(-changes, 0, None)
    out = np.full(close.shape, np.nan)
    avg_gain, avg_loss = math.fsum(gains[:period]) / period, math.fsum(losses[:period]) / period
    out[period] = 100 * avg_gain / (avg_gain + avg_loss)
    for row in range(period + 1, len(close)):
        avg_gain = (avg_gain * (period - 1) + gains[row - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[row - 1]) / period
        out[row] = 100 * avg_gain / (avg_gain + avg_loss)
    return out


def test_sma_matches_the_reference_and_pandas(spy: pd.DataFrame) -> None:
    result = pyta.sma(spy, period=20)
    assert list(result.columns) == ["SMA"]
    np.testing.assert_allclose(result["SMA"].iloc[-3:], SMA_20, rtol=0, atol=TOLERANCE)
    expected = spy["Close"].rolling(20).mean()
    np.testing.assert_allclose(result["SMA"], expected, rtol=0, atol=TOLERANCE)


def test_rsi_matches_the_reference_and_a_wilder_loop(spy: pd.DataFrame) -> None:
    result = pyta.rsi(spy, period=14)["RSI"]
    np.testing.assert_allclose(result.iloc[-3:], RSI_14, rtol=0, atol=TOLERANCE)
    expected = wilder_rsi(spy["Close"].to_numpy(), 14)
    np.testing.assert_allclose(result, expected, rtol=0, atol=TOLERANCE)


def test_macd_matches_the_reference(spy: pd.DataFrame) -> None:
    result = pyta.macd(spy, fast=12, slow=26, signal=9)
    assert list(result.columns) == ["MACD", "MACD_Signal", "MACD_Hist"]
    np.testing.assert_allclose(result.iloc[-1], MACD_LAST, rtol=0, atol=TOLERANCE)
    assert result["MACD"].iloc[:25].isna().all()
    assert result["MACD"].iloc[25:].notna().all()
    assert result["MACD_Signal"].iloc[:33].isna().all()


def test_obv_matches_the_reference_and_numpy(spy: pd.DataFrame) -> None:
    result = pyta.obv(spy)["OBV"]
    assert result.iloc[-1] == OBV_LAST
    close, volume = spy["Close"].to_numpy(), spy["Volume"].to_numpy(dtype=float)
    expected = volume[0] + np.cumsum(np.sign(np.diff(close)) * volume[1:])
    np.testing.assert_array_equal(result.iloc[1:], expected)


def test_containers_give_identical_values(spy: pd.DataFrame) -> None:
    close = spy["Close"]
    from_array = pyta.rsi(close.to_numpy(), period=14)
    from_list = pyta.rsi(close.tolist(), period=14)
    from_series = pyta.rsi(close, period=14)
    from_dict = pyta.rsi({"close": close.tolist()}, period=14)
    from_json = pyta.rsi(json.dumps(close.tolist()), period=14, output="numpy")
    assert isinstance(from_array, np.ndarray)
    assert isinstance(from_list, list)
    assert isinstance(from_series, pd.Series)
    assert from_series.name == "RSI"
    pd.testing.assert_index_equal(from_series.index, spy.index)
    for other in (from_list, from_series, from_dict["rsi"], from_json):
        np.testing.assert_array_equal(from_array, np.asarray(other, dtype=float))


def test_outputs_chain_into_the_next_indicator(spy: pd.DataFrame) -> None:
    signal = pyta.macd(spy)["MACD_Signal"]
    smoothed = pyta.sma(signal, period=5)  # leading NaN warm-up is skipped
    assert smoothed.name == "SMA"
    valid = signal.dropna()
    np.testing.assert_allclose(
        smoothed.loc[valid.index], valid.rolling(5).mean(), rtol=0, atol=TOLERANCE
    )


def test_output_conversion_to_json_keeps_the_dates(spy: pd.DataFrame) -> None:
    text = pyta.sma(spy.iloc[-3:].tz_localize(None), period=2, output="json")
    assert text.startswith('{"Date":["2025-12-29","2025-12-30","2025-12-31"],"SMA":[null,')


def test_batch_results_equal_single_calls(spy: pd.DataFrame) -> None:
    frames = {"all": spy, "2025": spy.loc["2025-01-01":], "last 60": spy.iloc[-60:]}
    results = pyta.batch.macd(frames)
    for name, frame in frames.items():
        pd.testing.assert_frame_equal(results[name], pyta.macd(frame))


@pytest.mark.parametrize("name", ["sma", "rsi", "macd", "bbands", "cci", "stoch", "atr", "obv"])
def test_namespaces_are_the_same_functions(name: str) -> None:
    function = getattr(pyta, name)
    category = function.__module__.split(".")[2]  # pyta.indicators.<category>.<name>
    assert getattr(getattr(pyta, category), name) is function
    assert getattr(getattr(pyta.batch, category), name) is getattr(pyta.batch, name)
