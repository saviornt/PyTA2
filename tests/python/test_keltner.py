"""Keltner Channels numerics, containers, errors and batch through the public API."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# True ranges from row 1: 2, 2, 2, 3, 3, 2, 3 (see tests/fixtures/keltner_hand.csv).
HIGH = [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0, 13.0]
LOW = [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0, 10.0]
CLOSE = [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0, 11.0]
NAMES = ["keltner_upper", "keltner_middle", "keltner_lower"]


def small() -> dict[str, list[float]]:
    return {"high": HIGH, "low": LOW, "close": CLOSE}


def ema_and_atr(ohlcv: Ohlcv, period: int, atr_period: int, k: float) -> list[NDArray[np.float64]]:
    """Keltner Channels from PyTA's public EMA and ATR, as the definition states."""
    middle = pyta.ema(ohlcv.close, period)
    width = k * pyta.atr(ohlcv.columns(), atr_period)["atr"]
    upper, lower = middle + width, middle - width
    # The bands start with whichever of the two starts later.
    upper[: max(period - 1, atr_period)] = np.nan
    lower[: max(period - 1, atr_period)] = np.nan
    return [upper, middle, lower]


def test_known_values() -> None:
    # EMA 3 (multiplier 1/2): 11, 11, 12, 13, 13, 12; ATR 3: 2, 7/3, ...
    result = pyta.keltner(small(), period=3, atr_period=3, k=2.0)

    assert list(result) == NAMES
    assert np.isnan(result["keltner_middle"][:2]).all()
    assert result["keltner_middle"][2:] == [11.0, 11.0, 12.0, 13.0, 13.0, 12.0]
    for band in ("keltner_upper", "keltner_lower"):
        assert np.isnan(result[band][:3]).all()
    assert (result["keltner_upper"][3], result["keltner_lower"][3]) == (15.0, 7.0)
    assert result["keltner_upper"][4] == pytest.approx(12.0 + 14.0 / 3.0, rel=1e-12)
    assert result["keltner_lower"][4] == pytest.approx(12.0 - 14.0 / 3.0, rel=1e-12)


@pytest.mark.parametrize(
    ("period", "atr_period", "k"), [(20, 10, 2.0), (1, 1, 1.0), (5, 30, 1.5), (50, 3, 3.0)]
)
def test_equals_pyta_ema_and_atr_exactly_on_real_prices(
    ohlcv: Ohlcv, period: int, atr_period: int, k: float
) -> None:
    result = pyta.keltner(ohlcv.columns(), period, atr_period, k)

    expected = ema_and_atr(ohlcv, period, atr_period, k)
    for name, want in zip(NAMES, expected, strict=True):
        np.testing.assert_array_equal(result[name], want)


def test_defaults_are_twenty_ten_and_two(ohlcv: Ohlcv) -> None:
    default = pyta.keltner(ohlcv.columns())
    explicit = pyta.keltner(ohlcv.columns(), period=20, atr_period=10, k=2.0)

    for name in NAMES:
        np.testing.assert_array_equal(default[name], explicit[name])


@pytest.mark.parametrize(("period", "atr_period"), [(20, 10), (5, 30), (1, 1)])
def test_each_output_keeps_its_own_warm_up_and_lines_are_ordered(
    ohlcv: Ohlcv, period: int, atr_period: int
) -> None:
    upper, middle, lower = (pyta.keltner(ohlcv.columns(), period, atr_period)[n] for n in NAMES)
    start = max(period - 1, atr_period)

    assert np.isnan(middle[: period - 1]).all()
    assert np.isfinite(middle[period - 1 :]).all()
    for band in (upper, lower):
        assert np.isnan(band[:start]).all()
        assert np.isfinite(band[start:]).all()
    assert (lower[start:] < middle[start:]).all()
    assert (middle[start:] < upper[start:]).all()


def test_int_k_is_accepted() -> None:
    as_int = pyta.keltner(small(), 3, 3, 2)
    as_float = pyta.keltner(small(), 3, 3, 2.0)

    for name in NAMES:
        assert as_int[name][3:] == as_float[name][3:]


def test_flat_series_gives_three_equal_lines() -> None:
    flat = np.full(6, 105.0)

    for line in pyta.keltner(np.column_stack([flat, flat, flat]), period=3, atr_period=2):
        assert (line[2:] == 105.0).all()


def test_needs_enough_rows_for_both_averages() -> None:
    # max(period, atr_period + 1) rows.
    with pytest.raises(ValueError, match="at least 9 values are required, got 8"):
        pyta.keltner(small(), period=9, atr_period=3)
    with pytest.raises(ValueError, match="at least 9 values are required, got 8"):
        pyta.keltner(small(), period=3, atr_period=8)

    upper, middle, lower = pyta.keltner(np.column_stack([HIGH, LOW, CLOSE]), 8, 7)
    assert np.isnan(middle[:7]).all()
    assert np.isfinite([upper[7], middle[7], lower[7]]).all()


@pytest.mark.parametrize("value", [0, -1, 2**31])
def test_rejects_an_invalid_period(value: int) -> None:
    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.keltner(small(), period=value)
    with pytest.raises(ValueError, match="atr_period must be between 1 and"):
        pyta.keltner(small(), atr_period=value)


def test_rejects_a_non_integer_period() -> None:
    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.keltner(small(), period=2.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="atr_period must be an integer"):
        pyta.keltner(small(), atr_period=2.5)  # type: ignore[arg-type]


@pytest.mark.parametrize("k", [0, -1.0, float("nan"), float("inf")])
def test_rejects_a_k_that_is_not_a_finite_positive_number(k: float) -> None:
    with pytest.raises(ValueError, match="k must be a finite number greater than 0"):
        pyta.keltner(small(), 3, 3, k)


def test_rejects_a_k_of_the_wrong_type() -> None:
    with pytest.raises(TypeError, match="k must be a number"):
        pyta.keltner(small(), 3, 3, True)
    with pytest.raises(TypeError, match="k must be a number"):
        pyta.keltner(small(), 3, 3, "2")  # type: ignore[arg-type]


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.keltner({"high": LOW, "low": HIGH, "close": CLOSE}, 3, 3)


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; keltner uses"):
        pyta.keltner(ohlcv.columns(), column="close")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="keltner needs the columns high, low and close"):
        pyta.keltner({"high": HIGH, "low": LOW}, 3, 3)

    with pytest.raises(TypeError, match="keltner needs the columns high, low and close"):
        pyta.keltner(np.array(CLOSE), 3, 3)


def test_adj_close_stands_in_for_close() -> None:
    adjusted = pyta.keltner({"high": HIGH, "low": LOW, "adj_close": CLOSE}, 3, 3)
    plain = pyta.keltner(small(), 3, 3)

    for name in NAMES:
        np.testing.assert_array_equal(adjusted[name], plain[name])


def test_unnamed_input_takes_high_low_close_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE])

    by_rows = pyta.keltner(rows, 3, 3)
    by_columns = pyta.keltner(rows.T, 3, 3)

    assert isinstance(by_rows, tuple)
    assert len(by_rows) == 3
    for a, b in zip(by_rows, by_columns, strict=True):
        np.testing.assert_array_equal(a, b)
    assert (by_rows[0][3], by_rows[2][3]) == (15.0, 7.0)


def test_columns_override_assigns_names_by_role() -> None:
    with pytest.raises(ValueError, match="column 'Hi' is not a recognized column name"):
        pyta.keltner({"Hi": HIGH, "low": LOW, "close": CLOSE}, 3, 3, columns=["Hi", "low", "close"])

    result = pyta.keltner({"h": HIGH, "l": LOW, "c": CLOSE}, 3, 3, columns=["close", "low", "high"])
    assert result["keltner_middle"][2:] == [11.0, 11.0, 12.0, 13.0, 13.0, 12.0]


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (("high", "low", "close"), ("keltner_upper", "keltner_middle", "keltner_lower")),
        (("HIGH", "LOW", "CLOSE"), ("KELTNER_UPPER", "KELTNER_MIDDLE", "KELTNER_LOWER")),
        (("High", "Low", "Close"), ("Keltner_Upper", "Keltner_Middle", "Keltner_Lower")),
    ],
)
def test_output_names_follow_the_input_casing(
    columns: tuple[str, str, str], expected: tuple[str, ...]
) -> None:
    result = pyta.keltner(dict(zip(columns, (HIGH, LOW, CLOSE), strict=True)), 3, 3)

    assert tuple(result) == expected


def test_json_records_give_three_keys_per_record() -> None:
    records = json.dumps(
        [{"high": h, "low": lo, "close": c} for h, lo, c in zip(HIGH, LOW, CLOSE, strict=True)]
    )

    result = json.loads(pyta.keltner(records, 3, 3))

    assert len(result) == len(HIGH)
    assert result[2] == {"keltner_upper": None, "keltner_middle": 11.0, "keltner_lower": None}
    assert result[3]["keltner_upper"] == 15.0


@pytest.mark.pandas
def test_dataframe_gains_three_columns_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame(
        {"Open": ohlcv.open, "High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close},
        index=index,
    )

    result = pyta.keltner(frame)

    assert list(result.columns) == ["Keltner_Upper", "Keltner_Middle", "Keltner_Lower"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["Keltner_Middle"].to_numpy(), pyta.ema(ohlcv.close, 20))


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.keltner(ohlcv.columns(), output="json"))

    assert list(result) == NAMES
    assert result["keltner_upper"][19] == pyta.keltner(ohlcv.columns())["keltner_upper"][19]


def test_middle_line_can_be_chained(ohlcv: Ohlcv) -> None:
    middle = pyta.keltner(ohlcv.columns())["keltner_middle"]

    smoothed = pyta.sma(middle, period=5)

    assert np.isnan(smoothed[:23]).all()
    assert np.isfinite(smoothed[23:]).all()


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    gapped = {"high": ohlcv.high.copy(), "low": ohlcv.low.copy(), "close": ohlcv.close.copy()}
    gapped["high"][:4] = np.nan
    gapped["close"][:9] = np.nan

    result = pyta.keltner(gapped)
    trimmed = pyta.keltner({name: values[9:] for name, values in gapped.items()})

    for name in NAMES:
        assert np.isnan(result[name][:9]).all()
        np.testing.assert_array_equal(result[name][9:], trimmed[name])


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), small(), {"high": LOW, "low": HIGH, "close": CLOSE}]

    results = pyta.batch.keltner(datasets)

    single = pyta.keltner(ohlcv.columns())
    for name in NAMES:
        np.testing.assert_array_equal(results[0][name], single[name])
    assert isinstance(results[1], ValueError)
    assert "at least 20 values are required, got 8" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.volatility.keltner({"b": small(), "a": ohlcv.columns()}, 3, 3, 2.0)

    assert list(results) == ["b", "a"]
    assert (results["b"]["keltner_upper"][3], results["b"]["keltner_lower"][3]) == (15.0, 7.0)


def test_batch_unnamed_datasets_give_tuples() -> None:
    results = pyta.batch.keltner([np.column_stack([HIGH, LOW, CLOSE])], 3, 3)

    assert isinstance(results[0], tuple)
    np.testing.assert_array_equal(results[0][1][2:], [11.0, 11.0, 12.0, 13.0, 13.0, 12.0])


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="atr_period must be between 1 and"):
        pyta.batch.keltner([ohlcv.columns()], atr_period=0)
    with pytest.raises(ValueError, match="k must be a finite number greater than 0"):
        pyta.batch.keltner([ohlcv.columns()], k=0.0)
    with pytest.raises(ValueError, match="column= is for single-column indicators; keltner uses"):
        pyta.batch.keltner([ohlcv.columns()], column="close")  # type: ignore[arg-type]
