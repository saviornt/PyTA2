"""On-Balance Volume through the public API: values, errors, containers and batch."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# Up, down, equal, up: OBV starts at the first volume (see the Rust kernel tests).
CLOSE = [10.0, 11.0, 10.5, 10.5, 12.0]
VOLUME = [100.0, 200.0, 300.0, 400.0, 500.0]
EXPECTED = [100.0, 300.0, 0.0, 0.0, 500.0]

NEEDS = r"obv needs the columns close \(close or adj_close\) and volume"


def columns(**overrides: list[float]) -> dict[str, list[float]]:
    return {"close": CLOSE, "volume": VOLUME} | overrides


def reference_obv(ohlcv: Ohlcv) -> NDArray[np.float64]:
    """OBV computed independently of PyTA: signed volumes, cumulated."""
    sign = np.sign(np.diff(ohlcv.close))
    return np.cumsum(np.concatenate(([ohlcv.volume[0]], sign * ohlcv.volume[1:])))


def test_known_values() -> None:
    assert pyta.obv(columns())["obv"] == EXPECTED


def test_matches_an_independent_calculation_on_real_prices(ohlcv: Ohlcv) -> None:
    result = pyta.obv(ohlcv.columns())["obv"]

    # Whole volumes: both sums are exact.
    np.testing.assert_array_equal(result, reference_obv(ohlcv))
    assert np.isfinite(result).all()


def test_one_row_is_enough() -> None:
    assert pyta.obv({"close": [5.0], "volume": [7.0]})["obv"] == [7.0]


def test_zero_volume_is_valid() -> None:
    assert pyta.obv(columns(volume=[0.0] * 5))["obv"] == [0.0] * 5


def test_rejects_a_negative_volume_naming_the_column_and_row() -> None:
    with pytest.raises(ValueError, match="is negative") as error:
        pyta.obv({"Close": CLOSE, "Volume": [1.0, 2.0, -3.0, 4.0, 5.0]})

    assert str(error.value) == (
        "column 'Volume' (volume) is negative at index 2 (-3.0); "
        "volume must be zero or more on every row"
    )


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; obv uses"):
        pyta.obv(ohlcv.columns(), column="close")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=NEEDS):
        pyta.obv({"close": CLOSE, "high": CLOSE})

    with pytest.raises(TypeError, match=NEEDS):
        pyta.obv(np.array(CLOSE))


def test_adj_close_stands_in_for_a_missing_close() -> None:
    assert pyta.obv({"adj_close": CLOSE, "volume": VOLUME})["obv"] == EXPECTED


def test_unnamed_input_takes_close_then_volume_in_either_orientation() -> None:
    rows = np.column_stack([CLOSE, VOLUME])

    by_rows = pyta.obv(rows)

    np.testing.assert_array_equal(by_rows, pyta.obv(rows.T))
    np.testing.assert_array_equal(by_rows, EXPECTED)


def test_columns_override_assigns_names_by_role() -> None:
    data = {"c": CLOSE, "v": VOLUME}

    assert pyta.obv(data, columns=["volume", "close"])["obv"] == EXPECTED


def test_skips_a_leading_gap_and_carries_it_over() -> None:
    result = pyta.obv({"close": [None, *CLOSE], "volume": [None, *VOLUME]})

    assert np.isnan(result["obv"][0])
    assert result["obv"][1:] == EXPECTED


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("close", "volume"), "obv"),
        (("CLOSE", "VOLUME"), "OBV"),
        (("Close", "Volume"), "OBV"),
    ],
)
def test_output_name_follows_the_input_casing(names: tuple[str, str], expected: str) -> None:
    result = pyta.obv(dict(zip(names, (CLOSE, VOLUME), strict=True)))

    assert list(result) == [expected]


def test_json_records_gain_one_key() -> None:
    records = json.dumps([{"close": c, "volume": v} for c, v in zip(CLOSE, VOLUME, strict=True)])

    result = json.loads(pyta.obv(records))

    assert [row["obv"] for row in result] == EXPECTED


@pytest.mark.pandas
def test_dataframe_gains_a_column_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.close), freq="D")
    frame = pd.DataFrame(
        {"Open": ohlcv.open, "High": ohlcv.high, "Close": ohlcv.close, "Volume": ohlcv.volume},
        index=index,
    )

    result = pyta.obv(frame)

    assert list(result.columns) == ["OBV"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["OBV"].to_numpy(), reference_obv(ohlcv))


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.obv(ohlcv.columns(), output="json"))

    assert list(result) == ["obv"]
    assert result["obv"][10] == pyta.obv(ohlcv.columns())["obv"][10]


def test_obv_output_can_be_chained(ohlcv: Ohlcv) -> None:
    obv = pyta.obv(ohlcv.columns())["obv"]

    smoothed = pyta.ema(obv, period=20)

    assert np.isnan(smoothed[:19]).all()
    assert np.isclose(smoothed[19], obv[:20].mean(), rtol=1e-12)


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), columns(), columns(volume=[-1.0] * 5), {"close": CLOSE}]

    results = pyta.batch.obv(datasets)

    np.testing.assert_array_equal(results[0]["obv"], pyta.obv(ohlcv.columns())["obv"])
    assert results[1]["obv"] == EXPECTED
    assert isinstance(results[2], ValueError)
    assert "volume must be zero or more" in str(results[2])
    assert isinstance(results[3], ValueError)
    assert "obv needs the columns" in str(results[3])


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.volume.obv({"b": columns(), "a": ohlcv.columns()})

    assert list(results) == ["b", "a"]
    assert results["b"]["obv"] == EXPECTED


def test_batch_shared_arguments_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; obv uses"):
        pyta.batch.obv([ohlcv.columns()], column="close")  # type: ignore[arg-type]
