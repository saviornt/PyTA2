"""Chaikin Money Flow through the public API: values, warm-up, errors, containers and batch."""

import json

import numpy as np
import pyta
import pytest
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# Multipliers 1/2, 0, 1, 0 (one-price bar), -1/2, 1/2; money-flow volumes 50, 0,
# 300, 0, -250, 0 (see the Rust kernel tests).
HIGH = [10.0, 11.0, 12.0, 12.0, 13.0, 14.0]
LOW = [8.0, 9.0, 10.0, 12.0, 11.0, 12.0]
CLOSE = [9.5, 10.0, 12.0, 12.0, 11.5, 13.5]
VOLUME = [100.0, 200.0, 300.0, 400.0, 500.0, 0.0]
EXPECTED = [350.0 / 600.0, 300.0 / 900.0, 50.0 / 1200.0, -250.0 / 900.0]

NEEDS = r"cmf needs the columns high, low, close \(close or adj_close\) and volume"


def columns(**overrides: list[float]) -> dict[str, list[float]]:
    data = {"high": HIGH, "low": LOW, "close": CLOSE, "volume": VOLUME}
    return data | overrides


def reference_cmf(ohlcv: Ohlcv, period: int) -> NDArray[np.float64]:
    """CMF computed independently of PyTA, from a fresh sum over every window."""
    high, low, close = ohlcv.high, ohlcv.low, ohlcv.close
    range_ = high - low
    multiplier = np.divide(
        (close - low) - (high - close),
        range_,
        out=np.zeros_like(range_),
        where=range_ > 0,
    )
    flow = sliding_window_view(multiplier * ohlcv.volume, period).sum(axis=1)
    total = sliding_window_view(ohlcv.volume, period).sum(axis=1)
    out = np.full(close.shape[0], np.nan)
    out[period - 1 :] = flow / total
    return out


def test_known_values() -> None:
    result = pyta.cmf(columns(), period=3)["cmf"]

    assert np.isnan(result[:2]).all()
    assert result[2:] == EXPECTED


@pytest.mark.parametrize("period", [1, 3, 20, 21, 100, 300])
def test_matches_fresh_window_sums_on_real_prices(ohlcv: Ohlcv, period: int) -> None:
    result = np.asarray(pyta.cmf(ohlcv.columns(), period=period)["cmf"])

    np.testing.assert_allclose(
        result, reference_cmf(ohlcv, period), rtol=0, atol=1e-12, equal_nan=True
    )
    assert np.isnan(result[: period - 1]).all()
    assert (np.abs(result[period - 1 :]) <= 1.0).all()


def test_default_period_is_twenty(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(
        pyta.cmf(ohlcv.columns())["cmf"], pyta.cmf(ohlcv.columns(), 20)["cmf"]
    )


def test_a_window_without_volume_is_nan() -> None:
    volume = [10.0, 0.0, 0.0, 0.0, 20.0, 0.0]
    result = pyta.cmf(columns(volume=volume), period=3)["cmf"]

    assert result[2] == 0.5
    assert np.isnan(result[3])
    assert result[4:] == [-0.5, -0.5]


def test_one_price_bars_give_zero() -> None:
    flat = [7.0] * 4
    data = {"high": flat, "low": flat, "close": flat, "volume": [5.0] * 4}

    assert pyta.cmf(data, period=2)["cmf"][1:] == [0.0] * 3


def test_needs_period_rows() -> None:
    with pytest.raises(ValueError, match=r"period \(7\) exceeds the series length \(6\)"):
        pyta.cmf(columns(), period=7)

    assert pyta.cmf(columns(), period=6)["cmf"][5] == 100.0 / 1500.0


@pytest.mark.parametrize("period", [0, -1, 2**31])
def test_rejects_an_invalid_period(period: int) -> None:
    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.cmf(columns(), period=period)


def test_rejects_a_non_integer_period() -> None:
    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.cmf(columns(), period=2.5)  # type: ignore[arg-type]


def test_rejects_high_below_low_and_a_negative_volume() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.cmf(columns(high=LOW, low=HIGH), period=2)

    with pytest.raises(ValueError, match="volume must be zero or more on every row"):
        pyta.cmf(columns(volume=[1.0, 2.0, 3.0, -4.0, 5.0, 6.0]), period=2)


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; cmf uses"):
        pyta.cmf(ohlcv.columns(), column="close")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=NEEDS):
        pyta.cmf({"high": HIGH, "low": LOW, "close": CLOSE}, period=2)

    with pytest.raises(TypeError, match=NEEDS):
        pyta.cmf(np.array(CLOSE), period=2)


def test_unnamed_input_takes_high_low_close_volume_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE, VOLUME])

    by_rows = pyta.cmf(rows, period=3)

    np.testing.assert_array_equal(by_rows, pyta.cmf(rows.T, period=3))
    np.testing.assert_array_equal(by_rows[2:], EXPECTED)


def test_columns_override_assigns_names_by_role() -> None:
    data = {"h": HIGH, "l": LOW, "adj close": CLOSE, "v": VOLUME}

    result = pyta.cmf(data, 3, columns=["volume", "adj_close", "high", "low"])

    assert result["cmf"][2:] == EXPECTED


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("high", "low", "close", "volume"), "cmf"),
        (("HIGH", "LOW", "CLOSE", "VOLUME"), "CMF"),
        (("High", "Low", "Close", "Volume"), "CMF"),
    ],
)
def test_output_name_follows_the_input_casing(
    names: tuple[str, str, str, str], expected: str
) -> None:
    result = pyta.cmf(dict(zip(names, (HIGH, LOW, CLOSE, VOLUME), strict=True)), period=3)

    assert list(result) == [expected]


def test_json_records_gain_one_key() -> None:
    records = json.dumps(
        [
            {"high": h, "low": lo, "close": c, "volume": v}
            for h, lo, c, v in zip(HIGH, LOW, CLOSE, VOLUME, strict=True)
        ]
    )

    result = json.loads(pyta.cmf(records, period=3))

    assert result[0] == {"cmf": None}
    assert [row["cmf"] for row in result[2:]] == EXPECTED


@pytest.mark.pandas
def test_dataframe_gains_a_column_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.close), freq="D")
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

    result = pyta.cmf(frame)

    assert list(result.columns) == ["CMF"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["CMF"].to_numpy(), pyta.cmf(ohlcv.columns())["cmf"])


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.cmf(ohlcv.columns(), output="json"))

    assert list(result) == ["cmf"]
    assert result["cmf"][19] == pyta.cmf(ohlcv.columns())["cmf"][19]


def test_cmf_output_can_be_chained(ohlcv: Ohlcv) -> None:
    line = pyta.cmf(ohlcv.columns(), period=20)["cmf"]

    smoothed = pyta.sma(line, period=5)

    assert np.isnan(smoothed[:23]).all()
    np.testing.assert_allclose(smoothed[23:], sliding_window_view(line[19:], 5).mean(axis=1))


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), columns(), columns(volume=[-1.0] * 6)]

    results = pyta.batch.cmf(datasets, 20)

    np.testing.assert_array_equal(results[0]["cmf"], pyta.cmf(ohlcv.columns(), 20)["cmf"])
    assert isinstance(results[1], ValueError)
    assert "period (20) exceeds the series length (6)" in str(results[1])
    assert isinstance(results[2], ValueError)
    assert "volume must be zero or more" in str(results[2])


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.volume.cmf({"b": columns(), "a": ohlcv.columns()}, 3)

    assert list(results) == ["b", "a"]
    assert results["b"]["cmf"][2:] == EXPECTED


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.batch.cmf([ohlcv.columns()], 0)

    with pytest.raises(ValueError, match="column= is for single-column indicators; cmf uses"):
        pyta.batch.cmf([ohlcv.columns()], column="close")  # type: ignore[arg-type]
