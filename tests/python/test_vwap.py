"""VWAP through the public API: values, leading rows without volume, errors, containers, batch."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# Typical prices 10, 11, 12, 12, 14, 14; volumes 0, 0, 100, 300, 0, 200 (see the Rust
# kernel tests).
HIGH = [11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
LOW = [9.0, 10.0, 11.0, 11.0, 12.0, 13.0]
CLOSE = [10.0, 11.0, 12.0, 11.0, 15.0, 13.0]
VOLUME = [0.0, 0.0, 100.0, 300.0, 0.0, 200.0]
EXPECTED = [12.0, 12.0, 12.0, 7600.0 / 600.0]

NEEDS = r"vwap needs the columns high, low, close \(close or adj_close\) and volume"


def columns(**overrides: list[float]) -> dict[str, list[float]]:
    data = {"high": HIGH, "low": LOW, "close": CLOSE, "volume": VOLUME}
    return data | overrides


def reference_vwap(ohlcv: Ohlcv) -> NDArray[np.float64]:
    """VWAP computed independently of PyTA: plain cumulative sums."""
    typical = (ohlcv.high + ohlcv.low + ohlcv.close) / 3.0
    return np.cumsum(typical * ohlcv.volume) / np.cumsum(ohlcv.volume)


def test_known_values() -> None:
    result = pyta.vwap(columns())["vwap"]

    assert np.isnan(result[:2]).all()
    assert result[2:] == EXPECTED


def test_matches_a_cumulative_sum_on_real_prices(ohlcv: Ohlcv) -> None:
    result = np.asarray(pyta.vwap(ohlcv.columns())["vwap"])

    np.testing.assert_allclose(result, reference_vwap(ohlcv), rtol=1e-12, atol=0)
    # Between the lowest low and the highest high seen so far.
    assert (result <= np.maximum.accumulate(ohlcv.high)).all()
    assert (result >= np.minimum.accumulate(ohlcv.low)).all()


def test_is_nan_until_the_first_volume_and_throughout_without_volume() -> None:
    assert np.isnan(pyta.vwap(columns(volume=[0.0] * 6))["vwap"]).all()

    result = pyta.vwap(columns(volume=[0.0] * 5 + [4.0]))["vwap"]
    assert np.isnan(result[:5]).all()
    assert result[5] == 14.0


def test_one_row_is_its_typical_price() -> None:
    data = {"high": [12.0], "low": [9.0], "close": [10.5], "volume": [3.0]}

    assert pyta.vwap(data)["vwap"] == [10.5]


def test_rejects_high_below_low_and_a_negative_volume() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.vwap(columns(high=LOW, low=HIGH))

    with pytest.raises(ValueError, match="volume must be zero or more on every row"):
        pyta.vwap(columns(volume=[0.0, 0.0, 1.0, -1.0, 0.0, 0.0]))


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; vwap uses"):
        pyta.vwap(ohlcv.columns(), column="close")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=NEEDS):
        pyta.vwap({"high": HIGH, "low": LOW, "close": CLOSE})

    with pytest.raises(TypeError, match=NEEDS):
        pyta.vwap(np.array(CLOSE))


def test_unnamed_input_takes_high_low_close_volume_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE, VOLUME])

    by_rows = pyta.vwap(rows)

    np.testing.assert_array_equal(by_rows, pyta.vwap(rows.T))
    np.testing.assert_array_equal(by_rows[2:], EXPECTED)


def test_columns_override_assigns_names_by_role() -> None:
    data = {"h": HIGH, "l": LOW, "c": CLOSE, "v": VOLUME}

    assert pyta.vwap(data, columns=["volume", "close", "high", "low"])["vwap"][2:] == EXPECTED


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("high", "low", "close", "volume"), "vwap"),
        (("HIGH", "LOW", "CLOSE", "VOLUME"), "VWAP"),
        (("High", "Low", "Close", "Volume"), "VWAP"),
    ],
)
def test_output_name_follows_the_input_casing(
    names: tuple[str, str, str, str], expected: str
) -> None:
    result = pyta.vwap(dict(zip(names, (HIGH, LOW, CLOSE, VOLUME), strict=True)))

    assert list(result) == [expected]


def test_json_records_gain_one_key() -> None:
    records = json.dumps(
        [
            {"high": h, "low": lo, "close": c, "volume": v}
            for h, lo, c, v in zip(HIGH, LOW, CLOSE, VOLUME, strict=True)
        ]
    )

    result = json.loads(pyta.vwap(records))

    assert result[0] == {"vwap": None}
    assert [row["vwap"] for row in result[2:]] == EXPECTED


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

    result = pyta.vwap(frame)

    assert list(result.columns) == ["VWAP"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["VWAP"].to_numpy(), pyta.vwap(ohlcv.columns())["vwap"])


@pytest.mark.pandas
def test_a_session_reset_is_a_groupby_by_date() -> None:
    # The wiki's recipe: one VWAP per session, each cumulative from its first bar.
    pd = pytest.importorskip("pandas")
    index = pd.to_datetime(
        ["2024-01-02 09:30", "2024-01-02 09:31", "2024-01-03 09:30", "2024-01-03 09:31"]
    )
    frame = pd.DataFrame(
        {
            "high": [11.0, 13.0, 21.0, 23.0],
            "low": [9.0, 11.0, 19.0, 21.0],
            "close": [10.0, 12.0, 20.0, 22.0],
            "volume": [100.0, 300.0, 200.0, 200.0],
        },
        index=index,
    )

    result = frame.groupby(frame.index.date, group_keys=False).apply(pyta.vwap)

    assert result.index.equals(index)
    assert result["vwap"].tolist() == [10.0, 11.5, 20.0, 21.0]


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.vwap(ohlcv.columns(), output="json"))

    assert list(result) == ["vwap"]
    assert result["vwap"][10] == pyta.vwap(ohlcv.columns())["vwap"][10]


def test_vwap_output_can_be_chained(ohlcv: Ohlcv) -> None:
    line = pyta.vwap(ohlcv.columns())["vwap"]

    distance = pyta.roc(line, period=1)

    assert np.isnan(distance[0])
    assert np.isfinite(distance[1:]).all()


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), columns(), columns(volume=[-1.0] * 6)]

    results = pyta.batch.vwap(datasets)

    np.testing.assert_array_equal(results[0]["vwap"], pyta.vwap(ohlcv.columns())["vwap"])
    assert results[1]["vwap"][2:] == EXPECTED
    assert isinstance(results[2], ValueError)
    assert "volume must be zero or more" in str(results[2])


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.volume.vwap({"b": columns(), "a": ohlcv.columns()})

    assert list(results) == ["b", "a"]
    assert results["b"]["vwap"][2:] == EXPECTED


def test_batch_shared_arguments_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; vwap uses"):
        pyta.batch.vwap([ohlcv.columns()], column="close")  # type: ignore[arg-type]
