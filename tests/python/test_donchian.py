"""Donchian Channels numerics, containers, errors and batch through the public API."""

import json

import numpy as np
import pyta
import pytest
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# Windows of 3, current row included: highest highs 12, 14, 14, 14, 13;
# lowest lows 9, 9, 10, 8, 8 (see the Rust kernel tests).
HIGH = [11.0, 12.0, 11.0, 14.0, 13.0, 10.0, 12.0]
LOW = [9.0, 9.0, 10.0, 12.0, 11.0, 8.0, 10.0]
NAMES = ["donchian_upper", "donchian_middle", "donchian_lower"]


def reference_donchian(
    high: NDArray[np.float64], low: NDArray[np.float64], period: int
) -> list[NDArray[np.float64]]:
    """Donchian Channels computed independently of PyTA, by rescanning every window."""
    warm_up = np.full(period - 1, np.nan)
    upper = np.concatenate([warm_up, sliding_window_view(high, period).max(axis=1)])
    lower = np.concatenate([warm_up, sliding_window_view(low, period).min(axis=1)])
    return [upper, (upper + lower) / 2, lower]


def test_known_values() -> None:
    result = pyta.donchian({"high": HIGH, "low": LOW}, period=3)

    assert list(result) == NAMES
    for name in NAMES:
        assert np.isnan(result[name][:2]).all()
    assert result["donchian_upper"][2:] == [12.0, 14.0, 14.0, 14.0, 13.0]
    assert result["donchian_middle"][2:] == [10.5, 11.5, 12.0, 11.0, 10.5]
    assert result["donchian_lower"][2:] == [9.0, 9.0, 10.0, 8.0, 8.0]


def test_period_one_is_high_and_low() -> None:
    upper, middle, lower = pyta.donchian((np.array(HIGH), np.array(LOW)), period=1)

    np.testing.assert_array_equal(upper, HIGH)
    np.testing.assert_array_equal(lower, LOW)
    np.testing.assert_array_equal(middle, (np.array(HIGH) + np.array(LOW)) / 2)


@pytest.mark.parametrize("period", [1, 2, 20, 55, 200])
def test_matches_an_independent_calculation_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.donchian(ohlcv.columns(), period=period)

    for name, want in zip(NAMES, reference_donchian(ohlcv.high, ohlcv.low, period), strict=True):
        np.testing.assert_array_equal(result[name], want)


def test_default_period_is_twenty(ohlcv: Ohlcv) -> None:
    default = pyta.donchian(ohlcv.columns())
    explicit = pyta.donchian(ohlcv.columns(), 20)

    for name in NAMES:
        np.testing.assert_array_equal(default[name], explicit[name])


@pytest.mark.parametrize("period", [1, 20, 50])
def test_warm_up_is_period_minus_one_and_channels_are_ordered(ohlcv: Ohlcv, period: int) -> None:
    upper, middle, lower = (pyta.donchian(ohlcv.columns(), period=period)[name] for name in NAMES)

    for channel in (upper, middle, lower):
        assert np.isnan(channel[: period - 1]).all()
        assert np.isfinite(channel[period - 1 :]).all()
    valid = slice(period - 1, None)
    assert (lower[valid] <= middle[valid]).all()
    assert (middle[valid] <= upper[valid]).all()


def test_the_window_includes_the_current_row() -> None:
    # A new high on the last row is that row's upper channel; StockCharts'
    # Price Channels (the prior rows) would not include it until the next.
    upper, _, _ = pyta.donchian(([1.0, 2.0, 9.0], [0.5, 1.5, 0.1]), period=2)

    assert upper[2] == 9.0


def test_high_equal_to_low_gives_three_equal_channels() -> None:
    flat = np.full(6, 105.0)

    for channel in pyta.donchian(np.column_stack([flat, flat]), period=4):
        assert (channel[3:] == 105.0).all()


def test_needs_period_rows() -> None:
    rows = np.ones(19)

    with pytest.raises(ValueError, match=r"period \(20\) exceeds the series length \(19\)"):
        pyta.donchian((rows, rows), period=20)

    upper, _, _ = pyta.donchian((np.ones(20), np.ones(20)), period=20)
    assert np.isnan(upper[:19]).all()
    assert upper[19] == 1.0


@pytest.mark.parametrize("period", [0, -1, 2**31])
def test_rejects_an_invalid_period(period: int) -> None:
    rows = np.ones(20)

    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.donchian((rows, rows), period=period)


def test_rejects_a_non_integer_period() -> None:
    rows = np.ones(20)

    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.donchian((rows, rows), period=2.5)  # type: ignore[arg-type]


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.donchian({"high": LOW, "low": HIGH}, period=2)


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; donchian uses"):
        pyta.donchian(ohlcv.columns(), column="high")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="donchian needs the columns high and low; missing: low"):
        pyta.donchian({"high": HIGH, "close": LOW}, period=2)

    with pytest.raises(TypeError, match="donchian needs the columns high and low"):
        pyta.donchian(np.array(HIGH), period=2)


def test_unnamed_input_takes_high_then_low_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW])

    by_rows = pyta.donchian(rows, period=3)
    by_columns = pyta.donchian(rows.T, period=3)

    assert isinstance(by_rows, tuple)
    assert len(by_rows) == 3
    for a, b in zip(by_rows, by_columns, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(by_rows[0][2:], [12.0, 14.0, 14.0, 14.0, 13.0])


def test_columns_override_assigns_names_by_role() -> None:
    data = {"Hi": HIGH, "Lo": LOW, "high": LOW, "low": LOW}

    with pytest.raises(ValueError, match="column 'Hi' is not a recognized column name"):
        pyta.donchian(data, period=3, columns=["Hi", "Lo"])

    result = pyta.donchian({"h": HIGH, "l": LOW}, period=3, columns=["low", "high"])
    assert result["donchian_upper"][2:] == [12.0, 14.0, 14.0, 14.0, 13.0]


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (("high", "low"), ("donchian_upper", "donchian_middle", "donchian_lower")),
        (("HIGH", "LOW"), ("DONCHIAN_UPPER", "DONCHIAN_MIDDLE", "DONCHIAN_LOWER")),
        (("High", "Low"), ("Donchian_Upper", "Donchian_Middle", "Donchian_Lower")),
    ],
)
def test_output_names_follow_the_input_casing(
    columns: tuple[str, str], expected: tuple[str, ...]
) -> None:
    result = pyta.donchian(dict(zip(columns, (HIGH, LOW), strict=True)), period=3)

    assert tuple(result) == expected


def test_json_records_give_three_keys_per_record() -> None:
    records = json.dumps([{"high": h, "low": low} for h, low in zip(HIGH, LOW, strict=True)])

    result = json.loads(pyta.donchian(records, period=3))

    assert len(result) == len(HIGH)
    assert result[0] == {
        "donchian_upper": None,
        "donchian_middle": None,
        "donchian_lower": None,
    }
    assert result[2]["donchian_upper"] == 12.0


@pytest.mark.pandas
def test_dataframe_gains_three_columns_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame({"High": ohlcv.high, "Low": ohlcv.low}, index=index)

    result = pyta.donchian(frame)

    assert list(result.columns) == ["Donchian_Upper", "Donchian_Middle", "Donchian_Lower"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(
        result["Donchian_Upper"].to_numpy(), pyta.donchian(ohlcv.columns())["donchian_upper"]
    )


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.donchian(ohlcv.columns(), output="json"))

    assert list(result) == NAMES
    assert result["donchian_upper"][19] == pyta.donchian(ohlcv.columns())["donchian_upper"][19]


def test_middle_channel_can_be_chained(ohlcv: Ohlcv) -> None:
    middle = pyta.donchian(ohlcv.columns(), period=20)["donchian_middle"]

    smoothed = pyta.sma(middle, period=5)

    assert np.isnan(smoothed[:23]).all()
    np.testing.assert_allclose(smoothed[23:], sliding_window_view(middle[19:], 5).mean(axis=1))


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    gapped = {"high": ohlcv.high.copy(), "low": ohlcv.low.copy()}
    gapped["high"][:4] = np.nan
    gapped["low"][:9] = np.nan

    result = pyta.donchian(gapped, period=20)
    trimmed = pyta.donchian({name: values[9:] for name, values in gapped.items()}, period=20)

    for name in NAMES:
        assert np.isnan(result[name][: 9 + 19]).all()
        np.testing.assert_array_equal(result[name][9:], trimmed[name])


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    short = {"high": HIGH, "low": LOW}
    datasets = [ohlcv.columns(), short, {"high": LOW, "low": HIGH}]

    results = pyta.batch.donchian(datasets, 20)

    single = pyta.donchian(ohlcv.columns(), 20)
    for name in NAMES:
        np.testing.assert_array_equal(results[0][name], single[name])
    assert isinstance(results[1], ValueError)
    assert "period (20) exceeds the series length (7)" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    small = {"high": HIGH, "low": LOW}

    results = pyta.batch.volatility.donchian({"b": small, "a": ohlcv.columns()}, 3)

    assert list(results) == ["b", "a"]
    assert results["b"]["donchian_lower"][2:] == [9.0, 9.0, 10.0, 8.0, 8.0]


def test_batch_unnamed_datasets_give_tuples() -> None:
    results = pyta.batch.donchian([np.column_stack([HIGH, LOW])], 3)

    assert isinstance(results[0], tuple)
    np.testing.assert_array_equal(results[0][1][2:], [10.5, 11.5, 12.0, 11.0, 10.5])


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.batch.donchian([ohlcv.columns()], 0)

    with pytest.raises(ValueError, match="column= is for single-column indicators; donchian uses"):
        pyta.batch.donchian([ohlcv.columns()], column="high")  # type: ignore[arg-type]
