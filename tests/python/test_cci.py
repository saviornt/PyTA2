"""CCI numerics through the public API."""

import numpy as np
import pyta
import pytest
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from ohlcv_data import Ohlcv


def reference_cci(
    high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64], period: int
) -> NDArray[np.float64]:
    """CCI computed independently of PyTA (no zero rule; for real, moving prices)."""
    typical = (high + low + close) / 3.0
    windows = sliding_window_view(typical, period)
    mean = windows.mean(axis=1)
    deviation = np.abs(windows - mean[:, None]).mean(axis=1)
    out = np.full(typical.shape[0], np.nan)
    out[period - 1 :] = (typical[period - 1 :] - mean) / (0.015 * deviation)
    return out


def test_known_values() -> None:
    # Typical prices 1, 2, 3, 7: each window's CCI is 100 (see the Rust kernel tests).
    result = pyta.cci((np.array([3.0, 6.0, 9.0, 21.0]), np.zeros(4), np.zeros(4)), period=3)

    assert np.isnan(result[:2]).all()
    np.testing.assert_allclose(result[2:], [100.0, 100.0], rtol=1e-12)


@pytest.mark.parametrize("period", [2, 14, 20, 50, 200])
def test_matches_an_independent_calculation_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.cci(ohlcv.columns(), period=period)[f"cci_{period}"]

    np.testing.assert_allclose(
        result,
        reference_cci(ohlcv.high, ohlcv.low, ohlcv.close, period),
        rtol=1e-9,
        atol=1e-9,
        equal_nan=True,
    )


def test_default_period_is_fourteen(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(
        pyta.cci(ohlcv.columns())["cci_14"], pyta.cci(ohlcv.columns(), 14)["cci_14"]
    )


@pytest.mark.parametrize("period", [2, 14, 50])
def test_real_prices_stay_within_the_bound(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.cci(ohlcv.columns(), period=period)[f"cci_{period}"]

    assert np.isnan(result[: period - 1]).all()
    assert np.isfinite(result[period - 1 :]).all()
    # Period 2 reaches the bound exactly, so allow for rounding.
    assert (np.abs(result[period - 1 :]) <= period / 0.03 * (1 + 1e-9)).all()


def test_flat_prices_and_period_one_give_zero() -> None:
    flat = np.full(10, 5.0)
    moving = np.arange(1.0, 11.0)

    assert (pyta.cci(np.column_stack([flat, flat, flat]), period=4)[3:] == 0.0).all()
    assert pyta.cci((moving + 1, moving - 1, moving), period=1) == (0.0,) * 10


def test_needs_as_many_rows_as_the_period() -> None:
    rows = np.ones(13)

    with pytest.raises(ValueError, match="at least 14 values are required, got 13"):
        pyta.cci((rows, rows, rows), period=14)

    assert pyta.cci((np.ones(14), np.ones(14), np.ones(14)), period=14)[-1] == 0.0


@pytest.mark.parametrize("period", [0, -1, 2**31])
def test_rejects_an_invalid_period(period: int) -> None:
    rows = np.ones(20)

    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.cci((rows, rows, rows), period=period)


def test_rejects_a_non_integer_period() -> None:
    rows = np.ones(20)

    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.cci((rows, rows, rows), period=2.5)  # type: ignore[arg-type]


def test_cci_output_can_be_chained(ohlcv: Ohlcv) -> None:
    cci = pyta.cci(ohlcv.columns(), period=20)["cci_20"]

    smoothed = pyta.sma(cci, period=5)

    assert np.isnan(smoothed[:23]).all()
    np.testing.assert_allclose(smoothed[23:], sliding_window_view(cci[19:], 5).mean(axis=1))


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    # Columns with different warm-ups (4, 9 and 19 leading NaN), as chained outputs have.
    gapped = {name: ohlcv.columns()[name].copy() for name in ("high", "low", "close")}
    for name, gap in (("high", 4), ("low", 9), ("close", 19)):
        gapped[name][:gap] = np.nan

    result = pyta.cci(gapped, period=14)["cci_14"]

    assert np.isnan(result[: 19 + 13]).all()
    trimmed = {name: values[19:] for name, values in gapped.items()}
    np.testing.assert_array_equal(result[19:], pyta.cci(trimmed, period=14)["cci_14"])
