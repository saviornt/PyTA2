"""Volume ROC through the public API: values, default column, negative volume, batch."""

import json

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv

# Period 2: 50 / 100, 0 / 200, 300 / 50, 150 / 0 (a zero base gives 0, as TA-Lib).
VOLUME = [100.0, 200.0, 50.0, 0.0, 300.0, 150.0]
EXPECTED = [-50.0, -100.0, 500.0, 0.0]


def test_known_values() -> None:
    result = pyta.vroc(VOLUME, period=2)

    assert np.isnan(result[:2]).all()
    assert result[2:] == EXPECTED


def test_a_tiny_base_gives_zero_not_infinity() -> None:
    # A volume of 1e-300 is zero against 5e6, so the output stays finite.
    result = pyta.vroc([1e-300, 5.0e6, 0.0, 10.0], period=1)

    assert np.isfinite(result[1:]).all()
    assert result[1:] == [0.0, -100.0, 0.0]


def test_matches_roc_of_the_volume_column(ohlcv: Ohlcv) -> None:
    # The same shared kernel as ROC, so every value is identical.
    np.testing.assert_array_equal(
        pyta.vroc(ohlcv.columns())["vroc"], pyta.roc(ohlcv.volume, period=10)
    )


def test_default_period_is_ten(ohlcv: Ohlcv) -> None:
    np.testing.assert_array_equal(pyta.vroc(ohlcv.volume), pyta.vroc(ohlcv.volume, 10))
    assert np.isnan(pyta.vroc(ohlcv.volume)[:10]).all()


def test_uses_the_volume_column_by_default(ohlcv: Ohlcv) -> None:
    result = pyta.vroc(ohlcv.columns(), period=5)

    assert list(result) == ["vroc"]
    np.testing.assert_array_equal(result["vroc"], pyta.vroc(ohlcv.volume, period=5))
    # column= picks another one.
    np.testing.assert_array_equal(
        pyta.vroc(ohlcv.columns(), 5, column="close")["vroc"], pyta.roc(ohlcv.close, 5)
    )


def test_needs_period_plus_one_values() -> None:
    with pytest.raises(ValueError, match="at least 7 values are required, got 6"):
        pyta.vroc(VOLUME, period=6)

    assert pyta.vroc(VOLUME, period=5)[5] == 50.0


@pytest.mark.parametrize("period", [0, -1, 2**31])
def test_rejects_an_invalid_period(period: int) -> None:
    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.vroc(VOLUME, period=period)


def test_rejects_a_negative_volume_naming_the_column_and_row() -> None:
    volume = [100.0, 200.0, -300.0, 400.0]

    with pytest.raises(ValueError, match="is negative") as error:
        pyta.vroc({"Close": [1.0] * 4, "Volume": volume}, period=1)

    assert str(error.value) == (
        "column 'Volume' (volume) is negative at index 2 (-300.0); "
        "volume must be zero or more on every row"
    )


def test_negative_check_counts_rows_after_a_leading_gap() -> None:
    with pytest.raises(ValueError, match=r"is negative at index 3 \(-1\.0\)"):
        pyta.vroc({"volume": [None, 5.0, 6.0, -1.0]}, period=1)


@pytest.mark.pandas
def test_rejects_a_negative_named_volume_series() -> None:
    pd = pytest.importorskip("pandas")

    with pytest.raises(ValueError, match="column 'Volume' \\(volume\\) is negative"):
        pyta.vroc(pd.Series([1.0, -2.0, 3.0], name="Volume"), period=1)


def test_unnamed_or_other_columns_may_be_negative() -> None:
    # Only a column matched to the volume role is checked: a list has no role,
    # and an indicator's output (OBV is often negative) chains as a lone column.
    assert pyta.vroc([4.0, -2.0, 1.0], period=1)[1:] == [-150.0, -150.0]
    assert pyta.vroc({"obv": [4.0, -2.0, 1.0]}, period=1)["vroc"][1:] == [-150.0, -150.0]
    assert pyta.sma({"close": [-1.0, -3.0]}, 2)["sma"][1] == -2.0


def test_any_single_column_indicator_rejects_a_negative_volume_column() -> None:
    with pytest.raises(ValueError, match="volume must be zero or more on every row"):
        pyta.sma({"close": [1.0, 2.0], "vol": [3.0, -4.0]}, 2, column="volume")


def test_rejects_columns() -> None:
    with pytest.raises(ValueError, match="columns="):
        pyta.vroc({"volume": VOLUME}, columns=["volume"])  # type: ignore[arg-type]


def test_output_name_follows_the_volume_column_casing() -> None:
    for name, expected in [("volume", "vroc"), ("VOLUME", "VROC"), ("Volume", "VROC")]:
        assert list(pyta.vroc({"close": VOLUME, name: VOLUME}, 2)) == [expected]


def test_json_object_gains_one_key() -> None:
    result = json.loads(pyta.vroc(json.dumps({"volume": VOLUME}), 2))

    assert result["vroc"][:2] == [None, None]
    assert result["vroc"][2:] == EXPECTED


def test_vroc_output_can_be_chained(ohlcv: Ohlcv) -> None:
    line = pyta.vroc(ohlcv.volume, 10)

    smoothed = pyta.sma(line, 5)

    assert np.isnan(smoothed[:14]).all()
    assert np.isfinite(smoothed[14:]).all()


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), VOLUME, {"volume": [1.0, -1.0, 2.0]}]

    results = pyta.batch.vroc(datasets, 2)

    np.testing.assert_array_equal(results[0]["vroc"], pyta.vroc(ohlcv.columns(), 2)["vroc"])
    assert results[1][2:] == EXPECTED
    assert isinstance(results[2], ValueError)
    assert "volume must be zero or more" in str(results[2])


def test_batch_mapping_keeps_keys_and_order() -> None:
    results = pyta.batch.volume.vroc({"b": VOLUME, "a": VOLUME[::-1]}, 2)

    assert list(results) == ["b", "a"]
    assert results["b"][2:] == EXPECTED


def test_batch_shared_parameters_raise_for_the_whole_call() -> None:
    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.batch.vroc([VOLUME], 0)
