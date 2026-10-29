"""Stochastic Oscillator numerics, containers, errors and batch through the public API."""

import json

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv

# k 3: raw %K 75, 50, 75, 80, 50 from row 2; k_smooth 2: %K 62.5, 62.5, 77.5, 65 from
# row 3; d 2: %D 62.5, 70, 71.25 from row 4 (every value an exact double).
HIGH = [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0]
LOW = [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0]
CLOSE = [10.0, 11.0, 12.0, 11.5, 13.0, 14.0, 13.0]
NAMES = ["stoch_k", "stoch_d"]
STOCH_K = [62.5, 62.5, 77.5, 65.0]
STOCH_D = [62.5, 70.0, 71.25]


def small() -> dict[str, list[float]]:
    return {"high": HIGH, "low": LOW, "close": CLOSE}


def test_known_values() -> None:
    result = pyta.stoch(small(), k=3, k_smooth=2, d=2)

    assert list(result) == NAMES
    assert np.isnan(result["stoch_k"][:3]).all()
    assert result["stoch_k"][3:] == STOCH_K
    assert np.isnan(result["stoch_d"][:4]).all()
    assert result["stoch_d"][4:] == STOCH_D


def test_defaults_are_14_3_3(ohlcv: Ohlcv) -> None:
    default = pyta.stoch(ohlcv.columns())
    explicit = pyta.stoch(ohlcv.columns(), k=14, k_smooth=3, d=3)

    for name in NAMES:
        np.testing.assert_array_equal(default[name], explicit[name])
    assert np.isnan(default["stoch_k"][:15]).all()
    assert np.isfinite(default["stoch_k"][15])


@pytest.mark.parametrize(
    ("k", "k_smooth", "d"), [(1, 1, 1), (5, 3, 3), (14, 3, 3), (14, 1, 5), (100, 20, 30)]
)
def test_each_output_keeps_its_own_warm_up_and_stays_between_0_and_100(
    ohlcv: Ohlcv, k: int, k_smooth: int, d: int
) -> None:
    stoch_k, stoch_d = (pyta.stoch(ohlcv.columns(), k, k_smooth, d)[n] for n in NAMES)
    k_start, d_start = k + k_smooth - 2, k + k_smooth + d - 3

    assert np.isnan(stoch_k[:k_start]).all()
    assert np.isfinite(stoch_k[k_start:]).all()
    assert np.isnan(stoch_d[:d_start]).all()
    assert np.isfinite(stoch_d[d_start:]).all()
    for line in (stoch_k[k_start:], stoch_d[d_start:]):
        assert ((line >= -1e-9) & (line <= 100.0 + 1e-9)).all()


def test_no_smoothing_gives_the_fast_stochastic() -> None:
    stoch_k, stoch_d = pyta.stoch(np.column_stack([HIGH, LOW, CLOSE]), 3, 1, 1)

    assert stoch_k[2:].tolist() == [75.0, 50.0, 75.0, 80.0, 50.0]
    np.testing.assert_array_equal(stoch_d, stoch_k)


def test_d_is_the_moving_average_of_k(ohlcv: Ohlcv) -> None:
    result = pyta.stoch(ohlcv.columns(), 14, 3, 5)

    np.testing.assert_allclose(
        result["stoch_d"], pyta.sma(result["stoch_k"], 5), rtol=1e-12, equal_nan=True
    )


def test_needs_k_plus_k_smooth_plus_d_minus_2_rows() -> None:
    with pytest.raises(ValueError, match="at least 8 values are required, got 7"):
        pyta.stoch(small(), k=6, k_smooth=2, d=2)

    _, stoch_d = pyta.stoch(np.column_stack([HIGH, LOW, CLOSE]), 5, 2, 2)
    assert np.isnan(stoch_d[:6]).all()
    assert np.isfinite(stoch_d[6])


def test_flat_series_gives_zero() -> None:
    flat = np.full(10, 105.0)

    stoch_k, stoch_d = pyta.stoch(np.column_stack([flat, flat, flat]), 3, 2, 2)

    assert (stoch_k[3:] == 0.0).all()
    assert (stoch_d[4:] == 0.0).all()


def test_close_at_the_extremes_gives_0_and_100() -> None:
    result = pyta.stoch(
        {
            "high": [10.0, 11.0, 12.0, 12.0],
            "low": [8.0, 9.0, 10.0, 7.0],
            "close": [9.0, 10.0, 12.0, 7.0],
        },
        3,
        1,
        1,
    )

    assert result["stoch_k"][2:] == [100.0, 0.0]


@pytest.mark.parametrize("name", ["k", "k_smooth", "d"])
@pytest.mark.parametrize("value", [0, -1, 2**31])
def test_rejects_an_invalid_parameter(name: str, value: int) -> None:
    with pytest.raises(ValueError, match=f"^{name} must be between 1 and"):
        pyta.stoch(small(), **{name: value})


@pytest.mark.parametrize("name", ["k", "k_smooth", "d"])
def test_rejects_a_non_integer_parameter(name: str) -> None:
    with pytest.raises(TypeError, match=f"^{name} must be an integer"):
        pyta.stoch(small(), **{name: 2.5})
    with pytest.raises(TypeError, match=f"^{name} must be an integer"):
        pyta.stoch(small(), **{name: True})


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.stoch({"high": LOW, "low": HIGH, "close": CLOSE}, 3, 2, 2)


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; stoch uses"):
        pyta.stoch(ohlcv.columns(), column="close")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="stoch needs the columns high, low and close"):
        pyta.stoch({"high": HIGH, "low": LOW}, 3, 2, 2)

    with pytest.raises(TypeError, match="stoch needs the columns high, low and close"):
        pyta.stoch(np.array(CLOSE), 3, 2, 2)


def test_adj_close_stands_in_for_close() -> None:
    adjusted = pyta.stoch({"high": HIGH, "low": LOW, "adj_close": CLOSE}, 3, 2, 2)
    plain = pyta.stoch(small(), 3, 2, 2)

    for name in NAMES:
        np.testing.assert_array_equal(adjusted[name], plain[name])


def test_unnamed_input_takes_high_low_close_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE])

    by_rows = pyta.stoch(rows, 3, 2, 2)
    by_columns = pyta.stoch(rows.T, 3, 2, 2)

    assert isinstance(by_rows, tuple)
    assert len(by_rows) == 2
    for a, b in zip(by_rows, by_columns, strict=True):
        np.testing.assert_array_equal(a, b)
    assert by_rows[1][4:].tolist() == STOCH_D


def test_columns_override_assigns_names_by_role() -> None:
    with pytest.raises(ValueError, match="column 'Hi' is not a recognized column name"):
        pyta.stoch(
            {"Hi": HIGH, "low": LOW, "close": CLOSE}, 3, 2, 2, columns=["Hi", "low", "close"]
        )

    result = pyta.stoch(
        {"h": HIGH, "l": LOW, "c": CLOSE}, 3, 2, 2, columns=["close", "low", "high"]
    )
    assert result["stoch_k"][3:] == STOCH_K


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (("high", "low", "close"), ("stoch_k", "stoch_d")),
        (("HIGH", "LOW", "CLOSE"), ("STOCH_K", "STOCH_D")),
        (("High", "Low", "Close"), ("Stoch_K", "Stoch_D")),
    ],
)
def test_output_names_follow_the_input_casing(
    columns: tuple[str, str, str], expected: tuple[str, ...]
) -> None:
    result = pyta.stoch(dict(zip(columns, (HIGH, LOW, CLOSE), strict=True)), 3, 2, 2)

    assert tuple(result) == expected


def test_json_records_give_two_keys_per_record() -> None:
    records = json.dumps(
        [{"high": h, "low": lo, "close": c} for h, lo, c in zip(HIGH, LOW, CLOSE, strict=True)]
    )

    result = json.loads(pyta.stoch(records, 3, 2, 2))

    assert len(result) == len(HIGH)
    assert result[3] == {"stoch_k": 62.5, "stoch_d": None}
    assert result[6] == {"stoch_k": 65.0, "stoch_d": 71.25}


@pytest.mark.pandas
def test_dataframe_gains_two_columns_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame(
        {"Open": ohlcv.open, "High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close},
        index=index,
    )

    result = pyta.stoch(frame)

    assert list(result.columns) == ["Stoch_K", "Stoch_D"]
    assert result.index.equals(index)
    np.testing.assert_array_equal(
        result["Stoch_D"].to_numpy(), pyta.stoch(ohlcv.columns())["stoch_d"]
    )


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.stoch(ohlcv.columns(), output="json"))

    assert list(result) == NAMES
    assert result["stoch_d"][17] == pyta.stoch(ohlcv.columns())["stoch_d"][17]
    assert result["stoch_d"][16] is None


def test_stoch_can_be_chained(ohlcv: Ohlcv) -> None:
    stoch_d = pyta.stoch(ohlcv.columns())["stoch_d"]

    smoothed = pyta.sma(stoch_d, period=5)

    assert np.isnan(smoothed[:21]).all()
    assert np.isfinite(smoothed[21:]).all()


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    gapped = {"high": ohlcv.high.copy(), "low": ohlcv.low.copy(), "close": ohlcv.close.copy()}
    gapped["high"][:4] = np.nan
    gapped["close"][:9] = np.nan

    result = pyta.stoch(gapped)
    trimmed = pyta.stoch({name: values[9:] for name, values in gapped.items()})

    for name in NAMES:
        assert np.isnan(result[name][:9]).all()
        np.testing.assert_array_equal(result[name][9:], trimmed[name])


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), small(), {"high": LOW, "low": HIGH, "close": CLOSE}]

    results = pyta.batch.stoch(datasets)

    single = pyta.stoch(ohlcv.columns())
    for name in NAMES:
        np.testing.assert_array_equal(results[0][name], single[name])
    assert isinstance(results[1], ValueError)
    assert "at least 18 values are required, got 7" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.momentum.stoch({"b": small(), "a": ohlcv.columns()}, 3, 2, 2)

    assert list(results) == ["b", "a"]
    assert results["b"]["stoch_d"][4:] == STOCH_D


def test_batch_unnamed_datasets_give_tuples() -> None:
    results = pyta.batch.stoch([np.column_stack([HIGH, LOW, CLOSE])], 3, 2, 2)

    assert isinstance(results[0], tuple)
    assert results[0][0][3:].tolist() == STOCH_K


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="k_smooth must be between 1 and"):
        pyta.batch.stoch([ohlcv.columns()], k_smooth=0)
    with pytest.raises(ValueError, match="column= is for single-column indicators; stoch uses"):
        pyta.batch.stoch([ohlcv.columns()], column="close")  # type: ignore[arg-type]
