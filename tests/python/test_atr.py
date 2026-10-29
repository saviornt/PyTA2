"""ATR numerics, containers, errors and batch through the public API."""

import numpy as np
import pyta
import pytest
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# True ranges 3, 1, 4, 2 from row 1 (row 3 gaps up from close 10); ATR(2) is
# 2, 3, 2.5 (see the Rust kernel tests).
HIGH = [11.0, 12.0, 11.0, 14.0, 13.0]
LOW = [9.0, 9.0, 10.0, 12.0, 11.0]
CLOSE = [10.0, 11.0, 10.0, 13.0, 12.0]


def reference_atr(
    high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64], period: int
) -> NDArray[np.float64]:
    """ATR computed independently of PyTA, in TA-Lib's form of Wilder's smoothing."""
    previous = close[:-1]
    ranges = np.maximum.reduce(
        [high[1:] - low[1:], np.abs(high[1:] - previous), np.abs(low[1:] - previous)]
    )
    out = np.full(close.shape[0], np.nan)
    average = float(ranges[:period].mean())
    out[period] = average
    for index in range(period, ranges.shape[0]):
        average = (average * (period - 1) + float(ranges[index])) / period
        out[index + 1] = average
    return out


def test_known_values() -> None:
    result = pyta.atr({"high": HIGH, "low": LOW, "close": CLOSE}, period=2)

    assert list(result) == ["atr"]
    assert np.isnan(result["atr"][:2]).all()
    assert result["atr"][2:] == [2.0, 3.0, 2.5]


def test_period_one_is_the_true_range() -> None:
    result = pyta.atr((np.array(HIGH), np.array(LOW), np.array(CLOSE)), period=1)

    assert np.isnan(result[0])
    np.testing.assert_array_equal(result[1:], [3.0, 1.0, 4.0, 2.0])


@pytest.mark.parametrize("period", [1, 2, 14, 50, 200])
def test_matches_an_independent_calculation_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.atr(ohlcv.columns(), period=period)["atr"]

    np.testing.assert_allclose(
        result,
        reference_atr(ohlcv.high, ohlcv.low, ohlcv.close, period),
        rtol=1e-9,
        atol=0,
        equal_nan=True,
    )


def test_default_period_is_fourteen(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(
        pyta.atr(ohlcv.columns())["atr"], pyta.atr(ohlcv.columns(), 14)["atr"]
    )


@pytest.mark.parametrize("period", [1, 14, 50])
def test_warm_up_is_period_rows_and_values_are_positive(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.atr(ohlcv.columns(), period=period)["atr"]

    assert np.isnan(result[:period]).all()
    assert (result[period:] > 0.0).all()


def test_flat_prices_give_zero() -> None:
    flat = np.full(10, 5.0)

    assert (pyta.atr(np.column_stack([flat, flat, flat]), period=4)[4:] == 0.0).all()


def test_high_equal_to_low_measures_only_the_gaps() -> None:
    steps = np.array([10.0, 12.0, 14.0, 16.0])

    np.testing.assert_array_equal(pyta.atr((steps, steps, steps), period=2)[2:], [2.0, 2.0])


def test_needs_one_row_more_than_the_period() -> None:
    rows = np.ones(14)

    with pytest.raises(ValueError, match="at least 15 values are required, got 14"):
        pyta.atr((rows, rows, rows), period=14)

    assert pyta.atr((np.ones(15), np.ones(15), np.ones(15)), period=14)[-1] == 0.0


@pytest.mark.parametrize("period", [0, -1, 2**31])
def test_rejects_an_invalid_period(period: int) -> None:
    rows = np.ones(20)

    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.atr((rows, rows, rows), period=period)


def test_rejects_a_non_integer_period() -> None:
    rows = np.ones(20)

    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.atr((rows, rows, rows), period=2.5)  # type: ignore[arg-type]


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high"):
        pyta.atr({"high": LOW, "low": HIGH, "close": CLOSE}, period=2)


def test_rejects_column_and_a_missing_column(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; atr uses"):
        pyta.atr(ohlcv.columns(), column="close")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="atr needs the columns high, low and close"):
        pyta.atr({"high": HIGH, "close": CLOSE}, period=2)


def test_title_case_input_gives_an_upper_case_name(ohlcv: Ohlcv) -> None:
    data = {"High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close}

    result = pyta.atr(data)

    assert list(result) == ["ATR"]
    np.testing.assert_array_equal(result["ATR"], pyta.atr(ohlcv.columns())["atr"])


def test_atr_output_can_be_chained(ohlcv: Ohlcv) -> None:
    atr = pyta.atr(ohlcv.columns(), period=14)["atr"]

    smoothed = pyta.sma(atr, period=5)

    assert np.isnan(smoothed[:18]).all()
    np.testing.assert_allclose(smoothed[18:], sliding_window_view(atr[14:], 5).mean(axis=1))


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    gapped = {name: ohlcv.columns()[name].copy() for name in ("high", "low", "close")}
    for name, gap in (("high", 4), ("low", 9), ("close", 19)):
        gapped[name][:gap] = np.nan

    result = pyta.atr(gapped, period=14)["atr"]

    assert np.isnan(result[: 19 + 14]).all()
    trimmed = {name: values[19:] for name, values in gapped.items()}
    np.testing.assert_array_equal(result[19:], pyta.atr(trimmed, period=14)["atr"])


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    short = {"high": HIGH, "low": LOW, "close": CLOSE}
    datasets = [ohlcv.columns(), short, {"high": LOW, "low": HIGH, "close": CLOSE}]

    results = pyta.batch.atr(datasets, 14)

    np.testing.assert_array_equal(results[0]["atr"], pyta.atr(ohlcv.columns(), 14)["atr"])
    assert isinstance(results[1], ValueError)
    assert "at least 15 values are required, got 5" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    small = {"high": HIGH, "low": LOW, "close": CLOSE}

    results = pyta.batch.volatility.atr({"b": small, "a": ohlcv.columns()}, 2)

    assert list(results) == ["b", "a"]
    assert results["b"]["atr"][2:] == [2.0, 3.0, 2.5]


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.batch.atr([ohlcv.columns()], 0)

    with pytest.raises(ValueError, match="column= is for single-column indicators; atr uses"):
        pyta.batch.atr([ohlcv.columns()], column="close")  # type: ignore[arg-type]
