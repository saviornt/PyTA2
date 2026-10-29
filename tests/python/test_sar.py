"""Parabolic SAR numerics, parameters, containers, errors and batch through the public API."""

import json
import math

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv

# Acceleration 0.25 and maximum 0.5, so every step is exact in binary (the
# Rust kernel tests walk through each row). Long from SAR 8 and EP 12; row 3's
# low 9 equals the SAR and reverses to short (a tie reverses), writing the EP 14
# raised to the row's high 15; row 6 caps the factor at 0.5; row 7's high 12
# equals the SAR and reverses to long, writing the EP 6; row 8's low 6 equals the
# SAR and reverses again.
HIGH = [10.0, 12.0, 14.0, 15.0, 13.0, 12.0, 12.0, 12.0, 13.0]
LOW = [8.0, 9.0, 10.0, 9.0, 11.0, 7.0, 6.0, 10.0, 6.0]
EXPECTED = [math.nan, 8.0, 9.0, 15.0, 15.0, 15.0, 13.0, 6.0, 13.0]


def small() -> dict[str, list[float]]:
    return {"high": HIGH, "low": LOW}


def hl(ohlcv: Ohlcv) -> dict[str, np.ndarray]:
    return {"high": ohlcv.high, "low": ohlcv.low}


def test_known_values_with_reversals_on_ties() -> None:
    result = pyta.sar(small(), 0.25, 0.5)

    assert list(result) == ["sar"]
    np.testing.assert_array_equal(result["sar"], EXPECTED)


def test_first_direction_follows_ta_lib() -> None:
    # Row 1's low falls 1 and its high falls 0.2: short, SAR high[0].
    assert pyta.sar(([10.0, 9.8], [9.0, 8.0]))[1] == 10.0
    # A tie (both move 1) starts long; row 1's low 8 is below SAR low[0] 9, so
    # it reverses at once and writes the EP high[1] (a short start writes 8).
    assert pyta.sar(([10.0, 11.0], [9.0, 8.0]))[1] == 11.0


def test_defaults_are_ta_libs(ohlcv: Ohlcv) -> None:
    default = pyta.sar(hl(ohlcv))["sar"]
    explicit = pyta.sar(hl(ohlcv), acceleration=0.02, maximum=0.2)["sar"]

    np.testing.assert_array_equal(default, explicit)


@pytest.mark.parametrize(("acceleration", "maximum"), [(0.02, 0.2), (0.01, 0.1), (0.2, 0.2)])
def test_one_warm_up_row_and_never_inside_a_row(
    ohlcv: Ohlcv, acceleration: float, maximum: float
) -> None:
    values = pyta.sar(hl(ohlcv), acceleration, maximum)["sar"]

    assert np.isnan(values[0])
    assert np.isfinite(values[1:]).all()
    outside = (values[1:] <= ohlcv.low[1:]) | (values[1:] >= ohlcv.high[1:])
    assert outside.all()


def test_needs_two_rows() -> None:
    with pytest.raises(ValueError, match="at least 2 values are required, got 1"):
        pyta.sar({"high": [10.0], "low": [9.0]})

    values = pyta.sar(np.column_stack([HIGH[:2], LOW[:2]]), 0.25, 0.5)
    assert values.tolist()[1] == 8.0


def test_ints_are_accepted_as_parameters() -> None:
    result = pyta.sar(small(), np.float64(0.25), 1)

    assert result["sar"][1] == 8.0


@pytest.mark.parametrize("name", ["acceleration", "maximum"])
@pytest.mark.parametrize("value", [0, -0.02, math.nan, math.inf])
def test_rejects_parameters_that_are_not_finite_and_positive(name: str, value: float) -> None:
    with pytest.raises(ValueError, match=f"{name} must be a finite number greater than 0"):
        pyta.sar(small(), **{name: value})


@pytest.mark.parametrize("value", [True, "0.02", None])
def test_rejects_a_parameter_of_the_wrong_type(value: object) -> None:
    with pytest.raises(TypeError, match="acceleration must be a number"):
        pyta.sar(small(), acceleration=value)  # type: ignore[arg-type]


def test_rejects_an_acceleration_above_its_maximum() -> None:
    # TA-Lib lowers the acceleration to the maximum silently.
    with pytest.raises(
        ValueError,
        match=r"acceleration must be at most maximum, got acceleration=0\.3 and maximum=0\.2",
    ):
        pyta.sar(small(), acceleration=0.3)

    equal = pyta.sar(small(), 0.5, 0.5)
    assert np.isfinite(equal["sar"][1:]).all()


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.sar({"high": LOW, "low": HIGH})


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; sar uses"):
        pyta.sar(hl(ohlcv), column="high")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="sar needs the columns high and low; missing: low"):
        pyta.sar({"high": HIGH, "close": LOW})

    with pytest.raises(TypeError, match="sar needs the columns high and low"):
        pyta.sar(np.array(HIGH))


def test_extra_columns_are_ignored(ohlcv: Ohlcv) -> None:
    full = pyta.sar(ohlcv.columns())["sar"]

    np.testing.assert_array_equal(full, pyta.sar(hl(ohlcv))["sar"])


def test_unnamed_input_takes_high_low_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW])

    by_rows = pyta.sar(rows, 0.25, 0.5)
    by_columns = pyta.sar(rows.T, 0.25, 0.5)

    assert isinstance(by_rows, np.ndarray)
    np.testing.assert_array_equal(by_rows, EXPECTED)
    np.testing.assert_array_equal(by_columns, EXPECTED)
    assert pyta.sar((HIGH, LOW), 0.25, 0.5)[3] == 15.0


def test_columns_override_assigns_names_by_role() -> None:
    result = pyta.sar({"h": HIGH, "l": LOW}, 0.25, 0.5, columns=["low", "high"])

    np.testing.assert_array_equal(result["sar"], EXPECTED)


@pytest.mark.parametrize(
    ("columns", "expected"),
    [(("high", "low"), "sar"), (("HIGH", "LOW"), "SAR"), (("High", "Low"), "SAR")],
)
def test_output_name_follows_the_input_casing(columns: tuple[str, str], expected: str) -> None:
    result = pyta.sar(dict(zip(columns, (HIGH, LOW), strict=True)))

    assert list(result) == [expected]


def test_json_records_gain_a_sar_key() -> None:
    records = json.dumps([{"high": h, "low": lo} for h, lo in zip(HIGH, LOW, strict=True)])

    result = json.loads(pyta.sar(records, 0.25, 0.5))

    assert result[0] == {"sar": None}
    assert [record["sar"] for record in result[1:]] == EXPECTED[1:]


@pytest.mark.pandas
def test_dataframe_gains_a_sar_column_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame(
        {"Open": ohlcv.open, "High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close},
        index=index,
    )

    result = pyta.sar(frame)

    assert list(result.columns) == ["SAR"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["SAR"].to_numpy(), pyta.sar(hl(ohlcv))["sar"])


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.sar(hl(ohlcv), output="json"))

    assert list(result) == ["sar"]
    assert result["sar"][0] is None
    assert result["sar"][1] == pyta.sar(hl(ohlcv))["sar"][1]


def test_sar_can_be_chained(ohlcv: Ohlcv) -> None:
    values = pyta.sar(hl(ohlcv))["sar"]

    smoothed = pyta.sma(values, period=5)

    assert np.isnan(smoothed[:5]).all()
    assert np.isfinite(smoothed[5:]).all()


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    gapped = {"high": ohlcv.high.copy(), "low": ohlcv.low.copy()}
    gapped["high"][:4] = np.nan
    gapped["low"][:9] = np.nan

    result = pyta.sar(gapped)["sar"]
    trimmed = pyta.sar({name: values[9:] for name, values in gapped.items()})["sar"]

    assert np.isnan(result[:10]).all()
    np.testing.assert_array_equal(result[9:], trimmed)


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [hl(ohlcv), {"high": [10.0], "low": [9.0]}, {"high": LOW, "low": HIGH}]

    results = pyta.batch.sar(datasets)

    np.testing.assert_array_equal(results[0]["sar"], pyta.sar(hl(ohlcv))["sar"])
    assert isinstance(results[1], ValueError)
    assert "at least 2 values are required, got 1" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.trend.sar({"b": small(), "a": hl(ohlcv)}, 0.25, 0.5)

    assert list(results) == ["b", "a"]
    np.testing.assert_array_equal(results["b"]["sar"], EXPECTED)


def test_batch_unnamed_datasets_give_arrays() -> None:
    results = pyta.batch.sar([np.column_stack([HIGH, LOW])], 0.25, 0.5)

    np.testing.assert_array_equal(results[0], EXPECTED)


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="acceleration must be at most maximum"):
        pyta.batch.sar([hl(ohlcv)], acceleration=0.5, maximum=0.2)
    with pytest.raises(ValueError, match="maximum must be a finite number greater than 0"):
        pyta.batch.sar([hl(ohlcv)], maximum=-1.0)
    with pytest.raises(ValueError, match="column= is for single-column indicators; sar uses"):
        pyta.batch.sar([hl(ohlcv)], column="high")  # type: ignore[arg-type]
