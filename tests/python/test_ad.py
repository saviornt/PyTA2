"""Accumulation/Distribution through the public API: values, errors, containers and batch."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# Multipliers 1, -1, -0.5, a one-price bar (adds nothing), 0 (see the Rust kernel tests).
HIGH = [12.0, 12.0, 14.0, 10.0, 12.0]
LOW = [10.0, 10.0, 10.0, 10.0, 8.0]
CLOSE = [12.0, 10.0, 11.0, 10.0, 10.0]
VOLUME = [100.0, 40.0, 200.0, 500.0, 300.0]
EXPECTED = [100.0, 60.0, -40.0, -40.0, -40.0]

NEEDS = r"ad needs the columns high, low, close \(close or adj_close\) and volume"


def columns(**overrides: list[float]) -> dict[str, list[float]]:
    data = {"high": HIGH, "low": LOW, "close": CLOSE, "volume": VOLUME}
    return data | overrides


def reference_ad(ohlcv: Ohlcv) -> NDArray[np.float64]:
    """A/D computed independently of PyTA: money-flow volumes, cumulated."""
    high, low, close = ohlcv.high, ohlcv.low, ohlcv.close
    range_ = high - low
    multiplier = np.divide(
        (close - low) - (high - close),
        range_,
        out=np.zeros_like(range_),
        where=range_ > 0,
    )
    return np.cumsum(multiplier * ohlcv.volume)


def test_known_values() -> None:
    assert pyta.ad(columns())["ad"] == EXPECTED


def test_matches_an_independent_calculation_on_real_prices(ohlcv: Ohlcv) -> None:
    result = pyta.ad(ohlcv.columns())["ad"]

    # The same operations in the same order: NumPy's cumsum adds left to right.
    np.testing.assert_array_equal(result, reference_ad(ohlcv))


def test_one_price_bars_and_zero_volume_add_nothing() -> None:
    flat = [7.0] * 3
    assert (
        pyta.ad({"high": flat, "low": flat, "close": flat, "volume": [9.0] * 3})["ad"] == [0.0] * 3
    )

    assert pyta.ad(columns(volume=[0.0] * 5))["ad"] == [0.0] * 5


def test_rejects_high_below_low_and_a_negative_volume() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.ad(columns(high=LOW, low=HIGH))

    with pytest.raises(ValueError, match="is negative") as error:
        pyta.ad(columns(volume=[1.0, -2.0, 3.0, 4.0, 5.0]))

    assert str(error.value) == (
        "column 'volume' (volume) is negative at index 1 (-2.0); "
        "volume must be zero or more on every row"
    )


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; ad uses"):
        pyta.ad(ohlcv.columns(), column="close")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=NEEDS):
        pyta.ad({"high": HIGH, "low": LOW, "close": CLOSE})

    with pytest.raises(TypeError, match=NEEDS):
        pyta.ad(np.array(CLOSE))


def test_adj_close_stands_in_for_a_missing_close() -> None:
    data = {"high": HIGH, "low": LOW, "adj_close": CLOSE, "volume": VOLUME}

    assert pyta.ad(data)["ad"] == EXPECTED


def test_unnamed_input_takes_high_low_close_volume_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE, VOLUME])

    by_rows = pyta.ad(rows)

    np.testing.assert_array_equal(by_rows, pyta.ad(rows.T))
    np.testing.assert_array_equal(by_rows, EXPECTED)


def test_columns_override_assigns_names_by_role() -> None:
    data = {"h": HIGH, "l": LOW, "c": CLOSE, "v": VOLUME}

    assert pyta.ad(data, columns=["volume", "close", "high", "low"])["ad"] == EXPECTED


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("high", "low", "close", "volume"), "ad"),
        (("HIGH", "LOW", "CLOSE", "VOLUME"), "AD"),
        (("High", "Low", "Close", "Volume"), "AD"),
    ],
)
def test_output_name_follows_the_input_casing(
    names: tuple[str, str, str, str], expected: str
) -> None:
    result = pyta.ad(dict(zip(names, (HIGH, LOW, CLOSE, VOLUME), strict=True)))

    assert list(result) == [expected]


def test_json_records_gain_one_key() -> None:
    records = json.dumps(
        [
            {"high": h, "low": lo, "close": c, "volume": v}
            for h, lo, c, v in zip(HIGH, LOW, CLOSE, VOLUME, strict=True)
        ]
    )

    result = json.loads(pyta.ad(records))

    assert [row["ad"] for row in result] == EXPECTED


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

    result = pyta.ad(frame)

    assert list(result.columns) == ["AD"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["AD"].to_numpy(), reference_ad(ohlcv))


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.ad(ohlcv.columns(), output="json"))

    assert list(result) == ["ad"]
    assert result["ad"][10] == pyta.ad(ohlcv.columns())["ad"][10]


def test_ad_output_can_be_chained(ohlcv: Ohlcv) -> None:
    # The Chaikin Oscillator is EMA(3) - EMA(10) of A/D.
    line = np.asarray(pyta.ad(ohlcv.columns())["ad"])

    oscillator = np.asarray(pyta.ema(line, 3)) - np.asarray(pyta.ema(line, 10))

    assert np.isnan(oscillator[:9]).all()
    assert np.isfinite(oscillator[9:]).all()


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), columns(), columns(volume=[-1.0] * 5)]

    results = pyta.batch.ad(datasets)

    np.testing.assert_array_equal(results[0]["ad"], pyta.ad(ohlcv.columns())["ad"])
    assert results[1]["ad"] == EXPECTED
    assert isinstance(results[2], ValueError)
    assert "volume must be zero or more" in str(results[2])


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.volume.ad({"b": columns(), "a": ohlcv.columns()})

    assert list(results) == ["b", "a"]
    assert results["b"]["ad"] == EXPECTED


def test_batch_shared_arguments_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; ad uses"):
        pyta.batch.ad([ohlcv.columns()], column="close")  # type: ignore[arg-type]
