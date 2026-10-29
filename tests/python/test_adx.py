"""ADX (with +DI and -DI) numerics, containers, errors and batch through the public API."""

import json

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv

# Period 2: row 1 seeds +DM 2 and TR 3; row 2 gives the sums 2 (+DM) and 4.5 (TR);
# row 3 gives +DM sum 1, -DM sum 2 and TR sum 6.25.
HIGH = [10.0, 12.0, 13.0, 12.0]
LOW = [8.0, 9.0, 10.0, 8.0]
CLOSE = [9.0, 11.0, 12.0, 9.0]
NAMES = ["adx", "adx_plus_di", "adx_minus_di"]

# The same values in the kernel's order of operations, so they compare exactly.
PLUS_2 = 100.0 * (2.0 / 4.5)
PLUS_3, MINUS_3 = 100.0 * (1.0 / 6.25), 100.0 * (2.0 / 6.25)
DX_3 = 100.0 * ((MINUS_3 - PLUS_3) / (MINUS_3 + PLUS_3))
ADX_3 = (100.0 + DX_3) / 2.0


def small() -> dict[str, list[float]]:
    return {"high": HIGH, "low": LOW, "close": CLOSE}


def test_known_values() -> None:
    result = pyta.adx(small(), period=2)

    assert list(result) == NAMES
    assert np.isnan(result["adx"][:3]).all()
    assert result["adx"][3] == ADX_3
    assert np.isnan(result["adx_plus_di"][:2]).all()
    assert result["adx_plus_di"][2:] == [PLUS_2, PLUS_3]
    assert result["adx_minus_di"][2:] == [0.0, MINUS_3]
    assert result["adx_plus_di"][3] == pytest.approx(16.0, rel=1e-15)
    assert result["adx"][3] == pytest.approx(200.0 / 3.0, rel=1e-15)


def test_default_period_is_fourteen(ohlcv: Ohlcv) -> None:
    default = pyta.adx(ohlcv.columns())
    explicit = pyta.adx(ohlcv.columns(), period=14)

    for name in NAMES:
        np.testing.assert_array_equal(default[name], explicit[name])


@pytest.mark.parametrize("period", [2, 5, 14, 50, 150])
def test_each_output_keeps_its_own_warm_up_and_stays_between_0_and_100(
    ohlcv: Ohlcv, period: int
) -> None:
    adx, plus_di, minus_di = (pyta.adx(ohlcv.columns(), period)[n] for n in NAMES)

    assert np.isnan(adx[: 2 * period - 1]).all()
    assert np.isfinite(adx[2 * period - 1 :]).all()
    for di in (plus_di, minus_di):
        assert np.isnan(di[:period]).all()
        assert np.isfinite(di[period:]).all()
    for line in (adx[2 * period - 1 :], plus_di[period:], minus_di[period:]):
        assert ((line >= 0.0) & (line <= 100.0)).all()


def test_needs_twice_its_period() -> None:
    with pytest.raises(ValueError, match="at least 6 values are required, got 4"):
        pyta.adx(small(), period=3)

    adx, _, _ = pyta.adx(np.column_stack([HIGH, LOW, CLOSE]), 2)
    assert np.isfinite(adx[3])


def test_flat_series_gives_zero() -> None:
    flat = np.full(10, 105.0)

    adx, plus_di, minus_di = pyta.adx(np.column_stack([flat, flat, flat]), period=3)

    assert (plus_di[3:] == 0.0).all()
    assert (minus_di[3:] == 0.0).all()
    assert (adx[5:] == 0.0).all()


def test_dis_hold_their_values_on_a_flat_stretch(ohlcv: Ohlcv) -> None:
    flat = np.full(30, ohlcv.close[59])
    columns = {
        "high": np.concatenate([ohlcv.high[:60], flat]),
        "low": np.concatenate([ohlcv.low[:60], flat]),
        "close": np.concatenate([ohlcv.close[:60], flat]),
    }

    adx, plus_di, minus_di = (pyta.adx(columns)[n] for n in NAMES)

    # Row 60 still sees the move from row 59's range to the flat price.
    for di in (plus_di, minus_di):
        np.testing.assert_allclose(di[61:], di[61], rtol=1e-9)
    target = 100.0 * abs(plus_di[61] - minus_di[61]) / (plus_di[61] + minus_di[61])
    assert abs(adx[89] - target) < abs(adx[62] - target)


@pytest.mark.parametrize("value", [0, 1, -1, 2**31])
def test_rejects_an_invalid_period(value: int) -> None:
    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.adx(small(), period=value)


def test_rejects_a_non_integer_period() -> None:
    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.adx(small(), period=2.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.adx(small(), period=True)


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.adx({"high": LOW, "low": HIGH, "close": CLOSE}, 2)


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; adx uses"):
        pyta.adx(ohlcv.columns(), column="close")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="adx needs the columns high, low and close"):
        pyta.adx({"high": HIGH, "low": LOW}, 2)

    with pytest.raises(TypeError, match="adx needs the columns high, low and close"):
        pyta.adx(np.array(CLOSE), 2)


def test_adj_close_stands_in_for_close() -> None:
    adjusted = pyta.adx({"high": HIGH, "low": LOW, "adj_close": CLOSE}, 2)
    plain = pyta.adx(small(), 2)

    for name in NAMES:
        np.testing.assert_array_equal(adjusted[name], plain[name])


def test_unnamed_input_takes_high_low_close_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE])

    by_rows = pyta.adx(rows, 2)
    by_columns = pyta.adx(rows.T, 2)

    assert isinstance(by_rows, tuple)
    assert len(by_rows) == 3
    for a, b in zip(by_rows, by_columns, strict=True):
        np.testing.assert_array_equal(a, b)
    assert (by_rows[0][3], by_rows[1][3], by_rows[2][3]) == (ADX_3, PLUS_3, MINUS_3)


def test_columns_override_assigns_names_by_role() -> None:
    with pytest.raises(ValueError, match="column 'Hi' is not a recognized column name"):
        pyta.adx({"Hi": HIGH, "low": LOW, "close": CLOSE}, 2, columns=["Hi", "low", "close"])

    result = pyta.adx({"h": HIGH, "l": LOW, "c": CLOSE}, 2, columns=["close", "low", "high"])
    assert result["adx"][3] == ADX_3


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (("high", "low", "close"), ("adx", "adx_plus_di", "adx_minus_di")),
        (("HIGH", "LOW", "CLOSE"), ("ADX", "ADX_PLUS_DI", "ADX_MINUS_DI")),
        (("High", "Low", "Close"), ("ADX", "ADX_Plus_DI", "ADX_Minus_DI")),
    ],
)
def test_output_names_follow_the_input_casing(
    columns: tuple[str, str, str], expected: tuple[str, ...]
) -> None:
    result = pyta.adx(dict(zip(columns, (HIGH, LOW, CLOSE), strict=True)), 2)

    assert tuple(result) == expected


def test_json_records_give_three_keys_per_record() -> None:
    records = json.dumps(
        [{"high": h, "low": lo, "close": c} for h, lo, c in zip(HIGH, LOW, CLOSE, strict=True)]
    )

    result = json.loads(pyta.adx(records, 2))

    assert len(result) == len(HIGH)
    assert result[2] == {"adx": None, "adx_plus_di": PLUS_2, "adx_minus_di": 0.0}
    assert result[3]["adx"] == ADX_3


@pytest.mark.pandas
def test_dataframe_gains_three_columns_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame(
        {"Open": ohlcv.open, "High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close},
        index=index,
    )

    result = pyta.adx(frame)

    assert list(result.columns) == ["ADX", "ADX_Plus_DI", "ADX_Minus_DI"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["ADX"].to_numpy(), pyta.adx(ohlcv.columns())["adx"])


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.adx(ohlcv.columns(), output="json"))

    assert list(result) == NAMES
    assert result["adx"][27] == pyta.adx(ohlcv.columns())["adx"][27]
    assert result["adx"][26] is None


def test_adx_can_be_chained(ohlcv: Ohlcv) -> None:
    adx = pyta.adx(ohlcv.columns())["adx"]

    smoothed = pyta.sma(adx, period=5)

    assert np.isnan(smoothed[:31]).all()
    assert np.isfinite(smoothed[31:]).all()


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    gapped = {"high": ohlcv.high.copy(), "low": ohlcv.low.copy(), "close": ohlcv.close.copy()}
    gapped["high"][:4] = np.nan
    gapped["close"][:9] = np.nan

    result = pyta.adx(gapped)
    trimmed = pyta.adx({name: values[9:] for name, values in gapped.items()})

    for name in NAMES:
        assert np.isnan(result[name][:9]).all()
        np.testing.assert_array_equal(result[name][9:], trimmed[name])


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), small(), {"high": LOW, "low": HIGH, "close": CLOSE}]

    results = pyta.batch.adx(datasets)

    single = pyta.adx(ohlcv.columns())
    for name in NAMES:
        np.testing.assert_array_equal(results[0][name], single[name])
    assert isinstance(results[1], ValueError)
    assert "at least 28 values are required, got 4" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.trend.adx({"b": small(), "a": ohlcv.columns()}, 2)

    assert list(results) == ["b", "a"]
    assert results["b"]["adx"][3] == ADX_3


def test_batch_unnamed_datasets_give_tuples() -> None:
    results = pyta.batch.adx([np.column_stack([HIGH, LOW, CLOSE])], 2)

    assert isinstance(results[0], tuple)
    assert results[0][1][2:].tolist() == [PLUS_2, PLUS_3]


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.batch.adx([ohlcv.columns()], period=1)
    with pytest.raises(ValueError, match="column= is for single-column indicators; adx uses"):
        pyta.batch.adx([ohlcv.columns()], column="close")  # type: ignore[arg-type]
