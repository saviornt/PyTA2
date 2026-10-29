"""Money Flow Index through the public API: values, warm-up, errors, containers and batch."""

import json

import numpy as np
import pyta
import pytest
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# Six rows; typical prices 9, 10, 11, 10, 10, 12 and flows +2000, +3300,
# -4000, neither, +7200, so period 3 gives three values from row 3 (see the
# Rust kernel tests).
HIGH = [10.0, 11.0, 12.0, 11.0, 11.0, 13.0]
LOW = [8.0, 9.0, 10.0, 9.0, 9.0, 11.0]
CLOSE = [9.0, 10.0, 11.0, 10.0, 10.0, 12.0]
VOLUME = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0]
EXPECTED = [100.0 * (5300.0 / 9300.0), 100.0 * (3300.0 / 7300.0), 100.0 * (7200.0 / 11200.0)]


NEEDS = r"mfi needs the columns high, low, close \(close or adj_close\) and volume"


def columns(**overrides: list[float]) -> dict[str, list[float]]:
    data = {"high": HIGH, "low": LOW, "close": CLOSE, "volume": VOLUME}
    return data | overrides


def reference_mfi(ohlcv: Ohlcv, period: int) -> NDArray[np.float64]:
    """MFI computed independently of PyTA, with window sums rather than running ones."""
    typical = (ohlcv.high + ohlcv.low + ohlcv.close) / 3.0
    flow = typical[1:] * ohlcv.volume[1:]
    change = np.diff(typical)
    positive = sliding_window_view(np.where(change > 0, flow, 0.0), period).sum(axis=1)
    negative = sliding_window_view(np.where(change < 0, flow, 0.0), period).sum(axis=1)
    out = np.full(typical.shape[0], np.nan)
    out[period:] = 100.0 * positive / (positive + negative)
    return out


def test_known_values() -> None:
    result = pyta.mfi((np.array(HIGH), np.array(LOW), np.array(CLOSE), np.array(VOLUME)), period=3)

    assert np.isnan(result[:3]).all()
    np.testing.assert_array_equal(result[3:], EXPECTED)


@pytest.mark.parametrize("period", [2, 14, 50, 200])
def test_matches_an_independent_calculation_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = pyta.mfi(ohlcv.columns(), period=period)["mfi"]

    np.testing.assert_allclose(
        result, reference_mfi(ohlcv, period), rtol=1e-9, atol=1e-9, equal_nan=True
    )
    assert np.isnan(result[:period]).all()
    assert ((result[period:] >= 0.0) & (result[period:] <= 100.0)).all()


def test_default_period_is_fourteen(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(
        pyta.mfi(ohlcv.columns())["mfi"], pyta.mfi(ohlcv.columns(), 14)["mfi"]
    )


def test_a_window_without_money_flow_gives_zero() -> None:
    flat = [105.0] * 6
    assert pyta.mfi(columns(high=flat, low=flat, close=flat), period=3)["mfi"][3:] == [0.0] * 3

    assert pyta.mfi(columns(volume=[0.0] * 6), period=3)["mfi"][3:] == [0.0] * 3


def test_needs_period_plus_one_rows() -> None:
    with pytest.raises(ValueError, match="at least 7 values are required, got 6"):
        pyta.mfi(columns(), period=6)

    assert pyta.mfi(columns(), period=5)["mfi"][5] == 100.0 * (12500.0 / 16500.0)


@pytest.mark.parametrize("period", [0, 1, -1, 2**31])
def test_rejects_an_invalid_period(period: int) -> None:
    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.mfi(columns(), period=period)


def test_rejects_a_non_integer_period() -> None:
    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.mfi(columns(), period=2.5)  # type: ignore[arg-type]


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.mfi(columns(high=LOW, low=HIGH), period=2)


def test_rejects_a_negative_volume_naming_the_column_and_row() -> None:
    volume = [100.0, 200.0, -300.0, 400.0, 500.0, 600.0]

    with pytest.raises(ValueError, match="is negative") as error:
        pyta.mfi({"High": HIGH, "Low": LOW, "Close": CLOSE, "Volume": volume}, period=2)

    assert str(error.value) == (
        "column 'Volume' (volume) is negative at index 2 (-300.0); "
        "volume must be zero or more on every row"
    )


def test_zero_volume_is_valid() -> None:
    result = pyta.mfi(columns(volume=[0.0, 0.0, 300.0, 400.0, 500.0, 600.0]), period=2)

    # Row 2: flows 0 (row 1, no volume) and +3300.
    assert result["mfi"][2] == 100.0


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; mfi uses"):
        pyta.mfi(ohlcv.columns(), column="high")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=NEEDS):
        pyta.mfi({"high": HIGH, "low": LOW, "close": CLOSE}, period=2)

    with pytest.raises(TypeError, match=NEEDS):
        pyta.mfi(np.array(HIGH), period=2)


def test_adj_close_stands_in_for_a_missing_close() -> None:
    data = {"high": HIGH, "low": LOW, "adj_close": CLOSE, "volume": VOLUME}

    assert pyta.mfi(data, period=3)["mfi"][3:] == EXPECTED


def test_unnamed_input_takes_high_low_close_volume_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE, VOLUME])

    by_rows = pyta.mfi(rows, period=3)

    np.testing.assert_array_equal(by_rows, pyta.mfi(rows.T, period=3))
    np.testing.assert_array_equal(by_rows[3:], EXPECTED)


def test_columns_override_assigns_names_by_role() -> None:
    data = {"h": HIGH, "l": LOW, "c": CLOSE, "v": VOLUME}

    result = pyta.mfi(data, 3, columns=["volume", "close", "high", "low"])

    assert result["mfi"][3:] == EXPECTED


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("high", "low", "close", "volume"), "mfi"),
        (("HIGH", "LOW", "CLOSE", "VOLUME"), "MFI"),
        (("High", "Low", "Close", "Volume"), "MFI"),
    ],
)
def test_output_name_follows_the_input_casing(
    names: tuple[str, str, str, str], expected: str
) -> None:
    result = pyta.mfi(dict(zip(names, (HIGH, LOW, CLOSE, VOLUME), strict=True)), period=3)

    assert list(result) == [expected]


def test_json_records_gain_one_key() -> None:
    records = json.dumps(
        [
            {"high": h, "low": lo, "close": c, "volume": v}
            for h, lo, c, v in zip(HIGH, LOW, CLOSE, VOLUME, strict=True)
        ]
    )

    result = json.loads(pyta.mfi(records, period=3))

    assert result[0] == {"mfi": None}
    assert result[3] == {"mfi": EXPECTED[0]}


@pytest.mark.pandas
def test_dataframe_gains_a_column_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame(
        {
            "Open": ohlcv.open,
            "High": ohlcv.high,
            "Low": ohlcv.low,
            "Close": ohlcv.close,
            "Volume": ohlcv.volume,
        },
        index=index,
    )

    result = pyta.mfi(frame)

    assert list(result.columns) == ["MFI"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["MFI"].to_numpy(), pyta.mfi(ohlcv.columns())["mfi"])


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.mfi(ohlcv.columns(), output="json"))

    assert list(result) == ["mfi"]
    assert result["mfi"][14] == pyta.mfi(ohlcv.columns())["mfi"][14]


def test_mfi_output_can_be_chained(ohlcv: Ohlcv) -> None:
    mfi = pyta.mfi(ohlcv.columns(), period=14)["mfi"]

    smoothed = pyta.sma(mfi, period=5)

    assert np.isnan(smoothed[:18]).all()
    np.testing.assert_allclose(smoothed[18:], sliding_window_view(mfi[14:], 5).mean(axis=1))


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), columns(), columns(volume=[-1.0] * 6)]

    results = pyta.batch.mfi(datasets, 14)

    np.testing.assert_array_equal(results[0]["mfi"], pyta.mfi(ohlcv.columns(), 14)["mfi"])
    assert isinstance(results[1], ValueError)
    assert "at least 15 values are required, got 6" in str(results[1])
    assert isinstance(results[2], ValueError)
    assert "volume must be zero or more" in str(results[2])


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.momentum.mfi({"b": columns(), "a": ohlcv.columns()}, 3)

    assert list(results) == ["b", "a"]
    assert results["b"]["mfi"][3:] == EXPECTED


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.batch.mfi([ohlcv.columns()], 1)

    with pytest.raises(ValueError, match="column= is for single-column indicators; mfi uses"):
        pyta.batch.mfi([ohlcv.columns()], column="high")  # type: ignore[arg-type]
