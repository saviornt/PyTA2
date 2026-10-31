"""Aroon numerics, containers, errors and batch through the public API."""

import json

import numpy as np
import pyta
import pytest
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# Period 2 (factor 50), windows of 3 rows, ties to the newest row: highest
# highs on rows 1, 3, 3, 5, 5 and lowest lows on rows 0, 3, 3, 3, 5 (see the
# Rust kernel tests).
HIGH = [10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 13.0]
LOW = [7.0, 9.0, 9.5, 8.0, 10.0, 9.0, 11.0]
UP = [50.0, 100.0, 50.0, 100.0, 50.0]
DOWN = [0.0, 100.0, 50.0, 0.0, 50.0]
OSC = [50.0, 0.0, 0.0, 100.0, 0.0]
NAMES = ["aroon_up", "aroon_down", "aroon_osc"]


def reference_aroon(
    high: NDArray[np.float64], low: NDArray[np.float64], period: int
) -> list[NDArray[np.float64]]:
    """Aroon computed independently of PyTA, by rescanning every window of `period` + 1 rows.

    Clamped to [0, 100] and [-100, 100], as PyTA documents.
    """
    factor = 100.0 / period
    warm_up = np.full(period, np.nan)
    # argmax returns the first of equal values; reversing each window makes it the newest.
    since_high = sliding_window_view(high, period + 1)[:, ::-1].argmax(axis=1)
    since_low = sliding_window_view(low, period + 1)[:, ::-1].argmin(axis=1)
    up = np.minimum(factor * (period - since_high), 100.0)
    down = np.minimum(factor * (period - since_low), 100.0)
    # TA-Lib's AROONOSC: factor * (row of the highest high - row of the lowest low).
    osc = np.clip(factor * (since_low - since_high), -100.0, 100.0)
    return [np.concatenate([warm_up, line]) for line in (up, down, osc)]


def test_known_values() -> None:
    result = pyta.aroon({"high": HIGH, "low": LOW}, period=2)

    assert list(result) == NAMES
    for name in NAMES:
        assert np.isnan(result[name][:2]).all()
    assert result["aroon_up"][2:] == UP
    assert result["aroon_down"][2:] == DOWN
    assert result["aroon_osc"][2:] == OSC


@pytest.mark.parametrize("period", [2, 11, 14, 25, 100, 299])
def test_matches_an_independent_calculation_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.aroon(ohlcv.columns(), period=period)

    for name, want in zip(NAMES, reference_aroon(ohlcv.high, ohlcv.low, period), strict=True):
        np.testing.assert_array_equal(result[name], want)


def test_default_period_is_fourteen(ohlcv: Ohlcv) -> None:
    default = pyta.aroon(ohlcv.columns())
    explicit = pyta.aroon(ohlcv.columns(), 14)

    for name in NAMES:
        np.testing.assert_array_equal(default[name], explicit[name])


@pytest.mark.parametrize("period", [2, 14, 50])
def test_warm_up_is_period_and_values_are_bounded(ohlcv: Ohlcv, period: int) -> None:
    up, down, osc = (pyta.aroon(ohlcv.columns(), period=period)[name] for name in NAMES)

    for line in (up, down, osc):
        assert np.isnan(line[:period]).all()
        assert np.isfinite(line[period:]).all()
    valid = slice(period, None)
    assert ((up[valid] >= 0) & (up[valid] <= 100)).all()
    assert ((down[valid] >= 0) & (down[valid] <= 100)).all()
    np.testing.assert_allclose(osc[valid], up[valid] - down[valid], rtol=0, atol=1e-12)


@pytest.mark.parametrize("period", [11, 22, 39])
def test_a_new_extreme_reads_exactly_100_for_every_period(period: int) -> None:
    # (100 / 11) * 11 is 100.00000000000001 in IEEE doubles (TA-Lib writes it); PyTA clamps.
    assert (100.0 / period) * period > 100.0
    rising = np.arange(60, dtype=np.float64)
    falling = rising[::-1].copy()

    up, down, osc = pyta.aroon({"high": rising, "low": rising}, period=period).values()
    assert (up[period:] == 100.0).all()
    assert (down[period:] == 0.0).all()
    assert (osc[period:] == 100.0).all()
    up, down, osc = pyta.aroon({"high": falling, "low": falling}, period=period).values()
    assert (up[period:] == 0.0).all()
    assert (down[period:] == 100.0).all()
    assert (osc[period:] == -100.0).all()


def test_the_window_holds_period_plus_one_rows() -> None:
    # Period 3: the high on row 0 is still in row 3's window and gone from row 4's.
    up, _, _ = pyta.aroon(([20.0, 10.0, 11.0, 12.0, 13.0], [1.0, 2.0, 3.0, 4.0, 5.0]), period=3)

    assert up[3] == 0.0
    assert up[4] == 100.0


def test_a_flat_window_gives_one_hundred_both_ways() -> None:
    flat = np.full(20, 105.0)

    up, down, osc = pyta.aroon(np.column_stack([flat, flat]), period=14)

    assert (up[14:] == 100.0).all()
    assert (down[14:] == 100.0).all()
    assert (osc[14:] == 0.0).all()


def test_needs_period_plus_one_rows() -> None:
    rows = np.ones(14)

    with pytest.raises(ValueError, match="at least 15 values are required, got 14"):
        pyta.aroon((rows, rows), period=14)

    up, _, _ = pyta.aroon((np.ones(15), np.ones(15)), period=14)
    assert np.isnan(up[:14]).all()
    assert up[14] == 100.0


@pytest.mark.parametrize("period", [0, 1, -1, 2**31])
def test_rejects_an_invalid_period(period: int) -> None:
    rows = np.ones(20)

    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.aroon((rows, rows), period=period)


def test_rejects_a_non_integer_period() -> None:
    rows = np.ones(20)

    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.aroon((rows, rows), period=2.5)  # type: ignore[arg-type]


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.aroon({"high": LOW, "low": HIGH}, period=2)


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; aroon uses"):
        pyta.aroon(ohlcv.columns(), column="high")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="aroon needs the columns high and low; missing: low"):
        pyta.aroon({"high": HIGH, "close": LOW}, period=2)

    with pytest.raises(TypeError, match="aroon needs the columns high and low"):
        pyta.aroon(np.array(HIGH), period=2)


def test_unnamed_input_takes_high_then_low_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW])

    by_rows = pyta.aroon(rows, period=2)
    by_columns = pyta.aroon(rows.T, period=2)

    assert isinstance(by_rows, tuple)
    assert len(by_rows) == 3
    for a, b in zip(by_rows, by_columns, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(by_rows[0][2:], UP)


def test_columns_override_assigns_names_by_role() -> None:
    data = {"Hi": HIGH, "Lo": LOW, "high": LOW, "low": LOW}

    with pytest.raises(ValueError, match="column 'Hi' is not a recognized column name"):
        pyta.aroon(data, period=2, columns=["Hi", "Lo"])

    result = pyta.aroon({"h": HIGH, "l": LOW}, period=2, columns=["low", "high"])
    assert result["aroon_down"][2:] == DOWN


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (("high", "low"), ("aroon_up", "aroon_down", "aroon_osc")),
        (("HIGH", "LOW"), ("AROON_UP", "AROON_DOWN", "AROON_OSC")),
        (("High", "Low"), ("Aroon_Up", "Aroon_Down", "Aroon_Osc")),
    ],
)
def test_output_names_follow_the_input_casing(
    columns: tuple[str, str], expected: tuple[str, ...]
) -> None:
    result = pyta.aroon(dict(zip(columns, (HIGH, LOW), strict=True)), period=2)

    assert tuple(result) == expected


def test_json_records_give_three_keys_per_record() -> None:
    records = json.dumps([{"high": h, "low": low} for h, low in zip(HIGH, LOW, strict=True)])

    result = json.loads(pyta.aroon(records, period=2))

    assert len(result) == len(HIGH)
    assert result[0] == {"aroon_up": None, "aroon_down": None, "aroon_osc": None}
    assert result[5] == {"aroon_up": 100.0, "aroon_down": 0.0, "aroon_osc": 100.0}


@pytest.mark.pandas
def test_dataframe_gains_three_columns_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame({"High": ohlcv.high, "Low": ohlcv.low}, index=index)

    result = pyta.aroon(frame)

    assert list(result.columns) == ["Aroon_Up", "Aroon_Down", "Aroon_Osc"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(
        result["Aroon_Osc"].to_numpy(), pyta.aroon(ohlcv.columns())["aroon_osc"]
    )


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.aroon(ohlcv.columns(), output="json"))

    assert list(result) == NAMES
    assert result["aroon_up"][14] == pyta.aroon(ohlcv.columns())["aroon_up"][14]


def test_oscillator_can_be_chained(ohlcv: Ohlcv) -> None:
    osc = pyta.aroon(ohlcv.columns(), period=14)["aroon_osc"]

    smoothed = pyta.sma(osc, period=5)

    assert np.isnan(smoothed[:18]).all()
    np.testing.assert_allclose(smoothed[18:], sliding_window_view(osc[14:], 5).mean(axis=1))


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    gapped = {"high": ohlcv.high.copy(), "low": ohlcv.low.copy()}
    gapped["high"][:4] = np.nan
    gapped["low"][:9] = np.nan

    result = pyta.aroon(gapped, period=14)
    trimmed = pyta.aroon({name: values[9:] for name, values in gapped.items()}, period=14)

    for name in NAMES:
        assert np.isnan(result[name][: 9 + 14]).all()
        np.testing.assert_array_equal(result[name][9:], trimmed[name])


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    short = {"high": HIGH, "low": LOW}
    datasets = [ohlcv.columns(), short, {"high": LOW, "low": HIGH}]

    results = pyta.batch.aroon(datasets, 14)

    single = pyta.aroon(ohlcv.columns(), 14)
    for name in NAMES:
        np.testing.assert_array_equal(results[0][name], single[name])
    assert isinstance(results[1], ValueError)
    assert "at least 15 values are required, got 7" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    small = {"high": HIGH, "low": LOW}

    results = pyta.batch.trend.aroon({"b": small, "a": ohlcv.columns()}, 2)

    assert list(results) == ["b", "a"]
    assert results["b"]["aroon_osc"][2:] == OSC


def test_batch_unnamed_datasets_give_tuples() -> None:
    results = pyta.batch.aroon([np.column_stack([HIGH, LOW])], 2)

    assert isinstance(results[0], tuple)
    np.testing.assert_array_equal(results[0][1][2:], DOWN)


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.batch.aroon([ohlcv.columns()], 1)

    with pytest.raises(ValueError, match="column= is for single-column indicators; aroon uses"):
        pyta.batch.aroon([ohlcv.columns()], column="high")  # type: ignore[arg-type]
