"""TRIX numerics, containers and errors through the public API."""

import itertools
import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv


def reference_trix(prices: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """TRIX written out with plain Python floats: three seeded EMAs, then the one-row ROC."""

    def ema(values: list[float]) -> list[float]:
        k = 2.0 / (period + 1)
        # A plain left-to-right sum: Python's `sum` of floats is compensated.
        seed = 0.0
        for value in values[:period]:
            seed += value
        out = [seed / period]
        for value in values[period:]:
            out.append((value - out[-1]) * k + out[-1])
        return out

    ema3 = ema(ema(ema(prices.tolist())))
    out = np.full(prices.shape[0], np.nan)
    first = 3 * (period - 1) + 1
    out[first:] = [
        0.0 if before == 0.0 else (now / before - 1.0) * 100.0
        for before, now in itertools.pairwise(ema3)
    ]
    return out


def test_known_values() -> None:
    # Period 2 (see the Rust kernel tests): EMA3 4.1666.. then 5.0925.., so
    # TRIX is 200 / 9 percent on the last row.
    result = pyta.trix(np.array([1.0, 4.0, 7.0, 4.0, 7.0]), period=2)

    assert np.isnan(result[:4]).all()
    assert result[4] == pytest.approx(200 / 9, rel=1e-12)


@pytest.mark.parametrize("period", [2, 9, 15, 30, 80])
def test_matches_a_plain_reference_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.trix(ohlcv.close, period=period)
    first = 3 * (period - 1) + 1

    assert np.isnan(result[:first]).all()
    assert np.isfinite(result[first:]).all()
    # The same IEEE operations in the same order, so the doubles are equal.
    np.testing.assert_array_equal(result, reference_trix(ohlcv.close, period))


def test_is_the_one_row_roc_of_chained_emas(ohlcv: Ohlcv) -> None:
    # Chaining skips each EMA's warm-up, so this is the same cascade.
    ema3 = pyta.ema(pyta.ema(pyta.ema(ohlcv.close, 15), 15), 15)

    np.testing.assert_array_equal(pyta.trix(ohlcv.close, 15), pyta.roc(ema3, 1))


def test_default_period_is_thirty(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.trix(ohlcv.close), pyta.trix(ohlcv.close, period=30))


def test_period_one_is_the_one_row_roc(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.trix(ohlcv.close, 1), pyta.roc(ohlcv.close, 1))


def test_flat_prices_and_a_zero_previous_ema_give_zero() -> None:
    assert (pyta.trix(np.full(20, 7.5), period=3)[7:] == 0.0).all()
    # A zero previous EMA3 gives 0, not an infinity (as TA-Lib).
    assert pyta.trix([0.0, 0.0, 0.0, 0.0, 0.0, 3.0], period=2)[4:] == [0.0, 0.0]


def test_needs_three_times_the_period_minus_one_values() -> None:
    with pytest.raises(ValueError, match="at least 89 values are required, got 88"):
        pyta.trix(np.ones(88))

    assert pyta.trix(np.ones(89))[88] == 0.0


@pytest.mark.parametrize(
    ("period", "error", "message"),
    [
        (0, ValueError, "period must be between 1 and 2147483647, got 0"),
        (-3, ValueError, "period must be between 1 and 2147483647, got -3"),
        (2**31, ValueError, "period must be between 1 and 2147483647, got 2147483648"),
        (2.5, TypeError, "period must be an integer, got float"),
        (True, TypeError, "period must be an integer, not bool"),
    ],
)
def test_invalid_period(period: object, error: type[Exception], message: str) -> None:
    with pytest.raises(error, match=message):
        pyta.trix([1.0, 2.0, 3.0], period=period)  # type: ignore[arg-type]


def test_rejects_columns() -> None:
    with pytest.raises(ValueError, match="trix uses one column"):
        pyta.trix({"close": [1.0, 2.0]}, period=1, columns=["close"])  # type: ignore[arg-type]


def test_rejects_non_finite_input() -> None:
    with pytest.raises(ValueError, match=r"non-finite value .* at index 2"):
        pyta.trix([1.0, 2.0, np.inf, 4.0], period=1)


def test_dict_uses_the_close_and_names_the_output(ohlcv: Ohlcv) -> None:
    result = pyta.trix({"Open": ohlcv.open, "Close": ohlcv.close}, period=15)

    assert list(result) == ["TRIX"]
    np.testing.assert_array_equal(result["TRIX"], pyta.trix(ohlcv.close, 15))


def test_column_selects_another_input(ohlcv: Ohlcv) -> None:
    result = pyta.trix(ohlcv.columns(), period=5, column="volume")

    np.testing.assert_array_equal(result["trix"], pyta.trix(ohlcv.volume, 5))


@pytest.mark.pandas
def test_series_keeps_its_index_and_is_named(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.close), freq="D")

    result = pyta.trix(pd.Series(ohlcv.close, index=index, name="Close"), 15)

    assert result.name == "TRIX"
    assert result.index.equals(index)


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.trix(ohlcv.close.tolist(), 15, output="json"))

    assert result["trix"][43] == pyta.trix(ohlcv.close, 15)[43]
    assert result["trix"][42] is None


def test_signal_line_is_an_ema_of_trix(ohlcv: Ohlcv) -> None:
    trix = pyta.trix(ohlcv.close, 15)

    signal = pyta.ema(trix, 9)

    # TRIX starts at row 43, so its 9-row EMA starts at row 51.
    assert np.isnan(signal[:51]).all()
    assert signal[51] == pytest.approx(trix[43:52].mean(), rel=1e-12)


def test_chained_input_skips_the_leading_gap(ohlcv: Ohlcv) -> None:
    gapped = ohlcv.close.copy()
    gapped[:5] = np.nan

    result = pyta.trix(gapped, 3)

    assert np.isnan(result[: 5 + 7]).all()
    np.testing.assert_array_equal(result[5:], pyta.trix(ohlcv.close[5:], 3))


# --- batch ----------------------------------------------------------------------------------


def test_batch_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    results = pyta.batch.trix([ohlcv.close, np.ones(10), [1.0, np.nan, 2.0]], 15)

    np.testing.assert_array_equal(results[0], pyta.trix(ohlcv.close, 15))
    assert isinstance(results[1], ValueError)
    assert "at least 44 values are required, got 10" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.momentum.trix({"b": ohlcv.open, "a": ohlcv.close}, 15)

    assert list(results) == ["b", "a"]
    np.testing.assert_array_equal(results["a"], pyta.trix(ohlcv.close, 15))


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.batch.trix([ohlcv.close], 0)
