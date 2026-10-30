"""Ultimate Oscillator through the public API: values, warm-up, errors, containers and batch."""

import json

import numpy as np
import pyta
import pytest
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# Seven rows; rows 1-6 have buying pressure 2, 1, 1, 1, 3, 0 and true range
# 3, 2, 3, 2, 4, 2, so windows 1, 2, 3 give four values from row 3 (see the
# Rust kernel tests).
HIGH = [10.0, 12.0, 13.0, 11.0, 12.0, 15.0, 14.0]
LOW = [8.0, 9.0, 11.0, 9.0, 10.0, 11.0, 12.0]
CLOSE = [9.0, 11.0, 12.0, 10.0, 11.0, 14.0, 12.0]


def weighted(a: float, b: float, c: float) -> float:
    return 100.0 * ((4.0 * a + 2.0 * b + c) / 7.0)


EXPECTED = [
    weighted(1 / 3, 2 / 5, 4 / 8),
    weighted(1 / 2, 2 / 5, 3 / 7),
    weighted(3 / 4, 4 / 6, 5 / 9),
    weighted(0 / 2, 3 / 6, 4 / 8),
]


def reference_ultosc(ohlcv: Ohlcv, short: int, medium: int, long: int) -> NDArray[np.float64]:
    """The Ultimate Oscillator with window sums rather than running ones (no flat windows)."""
    previous = ohlcv.close[:-1]
    true_low = np.minimum(ohlcv.low[1:], previous)
    pressure = ohlcv.close[1:] - true_low
    true_range = np.maximum(ohlcv.high[1:], previous) - true_low

    def average(window: int) -> NDArray[np.float64]:
        sums = sliding_window_view(pressure, window).sum(axis=1)
        ranges = sliding_window_view(true_range, window).sum(axis=1)
        return (sums / ranges)[long - window :]

    out = np.full(ohlcv.close.shape[0], np.nan)
    out[long:] = 100.0 * (4.0 * average(short) + 2.0 * average(medium) + average(long)) / 7.0
    return out


def test_known_values() -> None:
    result = pyta.ultosc((np.array(HIGH), np.array(LOW), np.array(CLOSE)), 1, 2, 3)

    assert np.isnan(result[:3]).all()
    np.testing.assert_array_equal(result[3:], EXPECTED)


@pytest.mark.parametrize("windows", [(7, 14, 28), (1, 2, 3), (5, 10, 50), (20, 60, 200)])
def test_matches_an_independent_calculation_on_real_prices(
    ohlcv: Ohlcv, windows: tuple[int, int, int]
) -> None:
    result = pyta.ultosc(ohlcv.columns(), *windows)["ultosc"]
    long = windows[2]

    np.testing.assert_allclose(
        result, reference_ultosc(ohlcv, *windows), rtol=1e-9, atol=1e-9, equal_nan=True
    )
    assert np.isnan(result[:long]).all()
    assert ((result[long:] >= 0.0) & (result[long:] <= 100.0)).all()


def test_defaults_are_7_14_28(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(
        pyta.ultosc(ohlcv.columns())["ultosc"], pyta.ultosc(ohlcv.columns(), 7, 14, 28)["ultosc"]
    )


def test_a_flat_stretch_gives_zero() -> None:
    flat = [105.0] * 8
    assert pyta.ultosc((flat, flat, flat), 1, 2, 3)[3:] == (0.0,) * 5


def test_needs_long_plus_one_rows() -> None:
    with pytest.raises(ValueError, match="at least 8 values are required, got 7"):
        pyta.ultosc((HIGH, LOW, CLOSE), 1, 2, 7)

    assert np.isfinite(pyta.ultosc((HIGH, LOW, CLOSE), 2, 4, 6)[6])


@pytest.mark.parametrize(
    ("windows", "message"),
    [
        ((7, 7, 28), "short must be less than medium, got short=7 and medium=7"),
        ((14, 7, 28), "short must be less than medium, got short=14 and medium=7"),
        ((7, 28, 14), "medium must be less than long, got medium=28 and long=14"),
        ((7, 14, 14), "medium must be less than long, got medium=14 and long=14"),
    ],
)
def test_rejects_windows_out_of_order(windows: tuple[int, int, int], message: str) -> None:
    # TA-Lib sorts them silently; PyTA raises.
    with pytest.raises(ValueError, match=message):
        pyta.ultosc((HIGH, LOW, CLOSE), *windows)


@pytest.mark.parametrize(
    ("name", "windows"),
    [("short", (0, 2, 3)), ("medium", (1, 0, 3)), ("long", (1, 2, 0)), ("long", (1, 2, 2**31))],
)
def test_rejects_a_window_out_of_range(name: str, windows: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError, match=f"{name} must be between 1 and"):
        pyta.ultosc((HIGH, LOW, CLOSE), *windows)


def test_rejects_a_non_integer_window() -> None:
    with pytest.raises(TypeError, match="medium must be an integer"):
        pyta.ultosc((HIGH, LOW, CLOSE), 1, 2.5, 3)  # type: ignore[arg-type]


def test_native_function_rejects_windows_out_of_order_too() -> None:
    # Rust checks the same order, with the same message, for direct callers.
    from pyta import _native

    columns = [np.array(values) for values in (HIGH, LOW, CLOSE)]
    with pytest.raises(
        ValueError, match="short must be less than medium, got short=3 and medium=2"
    ):
        _native.ultosc(columns, 3, 2, 4)


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.ultosc({"high": LOW, "low": HIGH, "close": CLOSE}, 1, 2, 3)


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; ultosc uses"):
        pyta.ultosc(ohlcv.columns(), column="high")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="ultosc needs the columns high, low and close"):
        pyta.ultosc({"high": HIGH, "low": LOW}, 1, 2, 3)

    with pytest.raises(TypeError, match="ultosc needs the columns high, low and close"):
        pyta.ultosc(np.array(HIGH), 1, 2, 3)


def test_adj_close_stands_in_for_a_missing_close() -> None:
    result = pyta.ultosc({"high": HIGH, "low": LOW, "adj_close": CLOSE}, 1, 2, 3)

    assert result["ultosc"][3:] == EXPECTED


def test_unnamed_input_takes_high_low_close_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE])

    by_rows = pyta.ultosc(rows, 1, 2, 3)

    np.testing.assert_array_equal(by_rows, pyta.ultosc(rows.T, 1, 2, 3))
    np.testing.assert_array_equal(by_rows[3:], EXPECTED)


def test_columns_override_assigns_names_by_role() -> None:
    data = {"h": HIGH, "l": LOW, "c": CLOSE}

    result = pyta.ultosc(data, 1, 2, 3, columns=["close", "high", "low"])

    assert result["ultosc"][3:] == EXPECTED


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("high", "low", "close"), "ultosc"),
        (("HIGH", "LOW", "CLOSE"), "ULTOSC"),
        (("High", "Low", "Close"), "ULTOSC"),
    ],
)
def test_output_name_follows_the_input_casing(names: tuple[str, str, str], expected: str) -> None:
    result = pyta.ultosc(dict(zip(names, (HIGH, LOW, CLOSE), strict=True)), 1, 2, 3)

    assert list(result) == [expected]


def test_json_records_gain_one_key() -> None:
    records = json.dumps(
        [{"high": h, "low": lo, "close": c} for h, lo, c in zip(HIGH, LOW, CLOSE, strict=True)]
    )

    result = json.loads(pyta.ultosc(records, 1, 2, 3))

    assert result[0] == {"ultosc": None}
    assert result[3] == {"ultosc": EXPECTED[0]}


@pytest.mark.pandas
def test_dataframe_gains_a_column_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame({"High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close}, index=index)

    result = pyta.ultosc(frame)

    assert list(result.columns) == ["ULTOSC"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(
        result["ULTOSC"].to_numpy(), pyta.ultosc(ohlcv.columns())["ultosc"]
    )


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.ultosc(ohlcv.columns(), output="json"))

    assert list(result) == ["ultosc"]
    assert result["ultosc"][28] == pyta.ultosc(ohlcv.columns())["ultosc"][28]


def test_ultosc_output_can_be_chained(ohlcv: Ohlcv) -> None:
    ultosc = pyta.ultosc(ohlcv.columns())["ultosc"]

    smoothed = pyta.sma(ultosc, period=5)

    assert np.isnan(smoothed[:32]).all()
    np.testing.assert_allclose(smoothed[32:], sliding_window_view(ultosc[28:], 5).mean(axis=1))


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    short = {"high": HIGH, "low": LOW, "close": CLOSE}
    datasets = [ohlcv.columns(), short, {"high": LOW, "low": HIGH, "close": CLOSE}]

    results = pyta.batch.ultosc(datasets)

    np.testing.assert_array_equal(results[0]["ultosc"], pyta.ultosc(ohlcv.columns())["ultosc"])
    assert isinstance(results[1], ValueError)
    assert "at least 29 values are required, got 7" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    small = {"high": HIGH, "low": LOW, "close": CLOSE}

    results = pyta.batch.momentum.ultosc({"b": small, "a": ohlcv.columns()}, 1, 2, 3)

    assert list(results) == ["b", "a"]
    assert results["b"]["ultosc"][3:] == EXPECTED


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="short must be less than medium"):
        pyta.batch.ultosc([ohlcv.columns()], 14, 7, 28)

    with pytest.raises(ValueError, match="column= is for single-column indicators; ultosc uses"):
        pyta.batch.ultosc([ohlcv.columns()], column="high")  # type: ignore[arg-type]
