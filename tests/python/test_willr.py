"""Williams %R through the public API: values, warm-up, errors, containers and batch."""

import json

import numpy as np
import pyta
import pytest
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# Seven rows; period 3 gives -25, -66.6.., -25, -20, -50 from row 2 (see the
# Rust kernel tests).
HIGH = [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0]
LOW = [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0]
CLOSE = [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0]
EXPECTED = [1 / 4 * -100.0, 2 / 3 * -100.0, 1 / 4 * -100.0, 1 / 5 * -100.0, 2 / 4 * -100.0]


def reference_willr(
    high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64], period: int
) -> NDArray[np.float64]:
    """Williams %R computed independently of PyTA (real prices: no flat window, no clamp)."""
    highest = sliding_window_view(high, period).max(axis=1)
    lowest = sliding_window_view(low, period).min(axis=1)
    out = np.full(high.shape[0], np.nan)
    out[period - 1 :] = (highest - close[period - 1 :]) / (highest - lowest) * -100.0
    return out


def test_known_values() -> None:
    result = pyta.willr((np.array(HIGH), np.array(LOW), np.array(CLOSE)), period=3)

    assert np.isnan(result[:2]).all()
    np.testing.assert_array_equal(result[2:], EXPECTED)


@pytest.mark.parametrize("period", [2, 14, 50, 200])
def test_matches_an_independent_calculation_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.willr(ohlcv.columns(), period=period)["willr"]

    np.testing.assert_allclose(
        result,
        reference_willr(ohlcv.high, ohlcv.low, ohlcv.close, period),
        rtol=1e-12,
        atol=1e-12,
        equal_nan=True,
    )
    assert np.isnan(result[: period - 1]).all()
    assert ((result[period - 1 :] >= -100.0) & (result[period - 1 :] <= 0.0)).all()


def test_default_period_is_fourteen(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(
        pyta.willr(ohlcv.columns())["willr"], pyta.willr(ohlcv.columns(), 14)["willr"]
    )


def test_flat_window_gives_zero_and_a_close_outside_is_clamped() -> None:
    flat = np.full(6, 105.0)
    assert pyta.willr((flat, flat, flat), period=3)[2:] == (0.0,) * 4

    # Close above the window's high, then below its low (nothing checks it).
    result = pyta.willr(([10.0, 11.0, 11.0], [9.0, 9.5, 9.5], [9.5, 12.0, 8.0]), period=2)
    assert result[1:] == (0.0, -100.0)


def test_needs_as_many_rows_as_the_period() -> None:
    with pytest.raises(ValueError, match=r"period \(8\) exceeds the series length \(7\)"):
        pyta.willr((HIGH, LOW, CLOSE), period=8)

    assert pyta.willr((HIGH, LOW, CLOSE), period=7)[6] == 2 / 6 * -100.0


@pytest.mark.parametrize("period", [0, 1, -1, 2**31])
def test_rejects_an_invalid_period(period: int) -> None:
    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.willr((HIGH, LOW, CLOSE), period=period)


def test_rejects_a_non_integer_period() -> None:
    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.willr((HIGH, LOW, CLOSE), period=2.5)  # type: ignore[arg-type]


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.willr({"high": LOW, "low": HIGH, "close": CLOSE}, period=2)


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; willr uses"):
        pyta.willr(ohlcv.columns(), column="high")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="willr needs the columns high, low and close"):
        pyta.willr({"high": HIGH, "low": LOW}, period=2)

    with pytest.raises(TypeError, match="willr needs the columns high, low and close"):
        pyta.willr(np.array(HIGH), period=2)


def test_adj_close_stands_in_for_a_missing_close() -> None:
    result = pyta.willr({"high": HIGH, "low": LOW, "adj_close": CLOSE}, period=3)

    assert result["willr"][2:] == EXPECTED


def test_unnamed_input_takes_high_low_close_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE])

    by_rows = pyta.willr(rows, period=3)

    np.testing.assert_array_equal(by_rows, pyta.willr(rows.T, period=3))
    np.testing.assert_array_equal(by_rows[2:], EXPECTED)


def test_columns_override_assigns_names_by_role() -> None:
    result = pyta.willr({"h": HIGH, "l": LOW, "c": CLOSE}, 3, columns=["close", "high", "low"])

    assert result["willr"][2:] == EXPECTED


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (("high", "low", "close"), "willr"),
        (("HIGH", "LOW", "CLOSE"), "WILLR"),
        (("High", "Low", "Close"), "WILLR"),
    ],
)
def test_output_name_follows_the_input_casing(columns: tuple[str, str, str], expected: str) -> None:
    result = pyta.willr(dict(zip(columns, (HIGH, LOW, CLOSE), strict=True)), period=3)

    assert list(result) == [expected]


def test_json_records_gain_one_key() -> None:
    records = json.dumps(
        [{"high": h, "low": lo, "close": c} for h, lo, c in zip(HIGH, LOW, CLOSE, strict=True)]
    )

    result = json.loads(pyta.willr(records, period=3))

    assert result[0] == {"willr": None}
    assert result[2] == {"willr": -25.0}


@pytest.mark.pandas
def test_dataframe_gains_a_column_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame({"High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close}, index=index)

    result = pyta.willr(frame)

    assert list(result.columns) == ["WILLR"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["WILLR"].to_numpy(), pyta.willr(ohlcv.columns())["willr"])


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.willr(ohlcv.columns(), output="json"))

    assert list(result) == ["willr"]
    assert result["willr"][13] == pyta.willr(ohlcv.columns())["willr"][13]


def test_willr_output_can_be_chained(ohlcv: Ohlcv) -> None:
    willr = pyta.willr(ohlcv.columns(), period=14)["willr"]

    smoothed = pyta.sma(willr, period=5)

    assert np.isnan(smoothed[:17]).all()
    np.testing.assert_allclose(smoothed[17:], sliding_window_view(willr[13:], 5).mean(axis=1))


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    gapped = {name: ohlcv.columns()[name].copy() for name in ("high", "low", "close")}
    for name, gap in (("high", 4), ("low", 9), ("close", 19)):
        gapped[name][:gap] = np.nan

    result = pyta.willr(gapped, period=14)["willr"]

    assert np.isnan(result[: 19 + 13]).all()
    trimmed = {name: values[19:] for name, values in gapped.items()}
    np.testing.assert_array_equal(result[19:], pyta.willr(trimmed, period=14)["willr"])


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    short = {"high": HIGH, "low": LOW, "close": CLOSE}
    datasets = [ohlcv.columns(), short, {"high": LOW, "low": HIGH, "close": CLOSE}]

    results = pyta.batch.willr(datasets, 14)

    np.testing.assert_array_equal(results[0]["willr"], pyta.willr(ohlcv.columns(), 14)["willr"])
    assert isinstance(results[1], ValueError)
    assert "period (14) exceeds the series length (7)" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    small = {"high": HIGH, "low": LOW, "close": CLOSE}

    results = pyta.batch.momentum.willr({"b": small, "a": ohlcv.columns()}, 3)

    assert list(results) == ["b", "a"]
    assert results["b"]["willr"][2:] == EXPECTED


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.batch.willr([ohlcv.columns()], 1)

    with pytest.raises(ValueError, match="column= is for single-column indicators; willr uses"):
        pyta.batch.willr([ohlcv.columns()], column="high")  # type: ignore[arg-type]
