"""Ichimoku Cloud numerics, containers, errors and batch through the public API."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

# The first eight rows of tests/fixtures/ichimoku_hand.csv.
HIGH = [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0, 13.0]
LOW = [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0, 10.0]
CLOSE = [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0, 11.0]
NAMES = [
    "ichimoku_tenkan",
    "ichimoku_kijun",
    "ichimoku_senkou_a",
    "ichimoku_senkou_b",
    "ichimoku_chikou",
]
# tenkan 2, kijun 3, senkou 5 on the rows above, from each line's first row.
TENKAN_2 = [10.5, 11.5, 11.5, 12.0, 13.0, 13.5, 12.0]
KIJUN_3 = [11.0, 11.5, 12.0, 12.5, 13.0, 12.5]
SENKOU_A = [11.25, 11.5, 12.0, 12.75, 13.25, 12.25]
SENKOU_5 = [11.5, 12.5, 12.5, 12.5]


def small() -> dict[str, list[float]]:
    return {"high": HIGH, "low": LOW, "close": CLOSE}


def from_donchian(ohlcv: Ohlcv, tenkan: int, kijun: int, senkou: int) -> list[NDArray[np.float64]]:
    """The five lines from PyTA's public Donchian Channels, as the definition states."""

    def middle(period: int) -> NDArray[np.float64]:
        return pyta.donchian(ohlcv.columns(), period)["donchian_middle"]

    conversion, base = middle(tenkan), middle(kijun)
    return [conversion, base, (conversion + base) / 2, middle(senkou), np.array(ohlcv.close)]


def test_known_values() -> None:
    result = pyta.ichimoku(small(), tenkan=2, kijun=3, senkou=5)

    assert list(result) == NAMES
    for name, first, values in zip(
        NAMES, [1, 2, 2, 4, 0], [TENKAN_2, KIJUN_3, SENKOU_A, SENKOU_5, CLOSE], strict=True
    ):
        assert np.isnan(result[name][:first]).all()
        assert result[name][first:] == values


@pytest.mark.parametrize(
    ("tenkan", "kijun", "senkou"), [(9, 26, 52), (1, 1, 1), (30, 5, 2), (7, 22, 44)]
)
def test_equals_pyta_donchian_middles_exactly_on_real_prices(
    ohlcv: Ohlcv, tenkan: int, kijun: int, senkou: int
) -> None:
    result = pyta.ichimoku(ohlcv.columns(), tenkan, kijun, senkou)

    expected = from_donchian(ohlcv, tenkan, kijun, senkou)
    for name, want in zip(NAMES, expected, strict=True):
        np.testing.assert_array_equal(result[name], want)


def test_defaults_are_nine_twenty_six_and_fifty_two(ohlcv: Ohlcv) -> None:
    default = pyta.ichimoku(ohlcv.columns())
    explicit = pyta.ichimoku(ohlcv.columns(), tenkan=9, kijun=26, senkou=52)

    for name in NAMES:
        np.testing.assert_array_equal(default[name], explicit[name])


@pytest.mark.parametrize(("tenkan", "kijun", "senkou"), [(9, 26, 52), (30, 5, 2), (1, 1, 1)])
def test_each_output_keeps_its_own_warm_up(
    ohlcv: Ohlcv, tenkan: int, kijun: int, senkou: int
) -> None:
    result = pyta.ichimoku(ohlcv.columns(), tenkan, kijun, senkou)
    firsts = [tenkan - 1, kijun - 1, max(tenkan, kijun) - 1, senkou - 1, 0]

    for name, first in zip(NAMES, firsts, strict=True):
        assert len(result[name]) == len(ohlcv.close)
        assert np.isnan(result[name][:first]).all()
        assert np.isfinite(result[name][first:]).all()


def test_spans_shift_for_charting_with_pandas_style_offsets(ohlcv: Ohlcv) -> None:
    # Shifting the default (unshifted) output by hand, which keeps the future
    # cloud that `shift=True` drops: spans `kijun` rows ahead, chikou back.
    kijun = 26
    result = pyta.ichimoku(ohlcv.columns())
    span_a = np.concatenate([np.full(kijun, np.nan), result["ichimoku_senkou_a"]])
    chikou = result["ichimoku_chikou"][kijun:]

    assert span_a[kijun + 25] == result["ichimoku_senkou_a"][25]
    assert chikou[0] == ohlcv.close[kijun]


def test_flat_series_gives_one_level() -> None:
    flat = np.full(6, 105.0)

    for line in pyta.ichimoku(np.column_stack([flat, flat, flat]), 2, 3, 4):
        assert (line[3:] == 105.0).all()


def test_needs_rows_for_its_longest_window() -> None:
    for windows in [(9, 3, 5), (2, 9, 5), (2, 3, 9)]:
        with pytest.raises(ValueError, match="at least 9 values are required, got 8"):
            pyta.ichimoku(small(), *windows)

    lines = pyta.ichimoku(np.column_stack([HIGH, LOW, CLOSE]), 2, 3, 8)
    assert np.isfinite([line[7] for line in lines]).all()


@pytest.mark.parametrize("name", ["tenkan", "kijun", "senkou"])
@pytest.mark.parametrize("value", [0, -1, 2**31])
def test_rejects_an_invalid_window(name: str, value: int) -> None:
    with pytest.raises(ValueError, match=f"{name} must be between 1 and"):
        pyta.ichimoku(small(), **{name: value})


@pytest.mark.parametrize("name", ["tenkan", "kijun", "senkou"])
def test_rejects_a_non_integer_window(name: str) -> None:
    with pytest.raises(TypeError, match=f"{name} must be an integer"):
        pyta.ichimoku(small(), **{name: 2.5})
    with pytest.raises(TypeError, match=f"{name} must be an integer"):
        pyta.ichimoku(small(), **{name: True})


def test_rejects_high_below_low() -> None:
    with pytest.raises(ValueError, match="high must be at least low"):
        pyta.ichimoku({"high": LOW, "low": HIGH, "close": CLOSE}, 2, 3, 5)


def test_rejects_column_a_missing_column_and_one_series(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; ichimoku uses"):
        pyta.ichimoku(ohlcv.columns(), column="close")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="ichimoku needs the columns high, low and close"):
        pyta.ichimoku({"high": HIGH, "low": LOW}, 2, 3, 5)

    with pytest.raises(TypeError, match="ichimoku needs the columns high, low and close"):
        pyta.ichimoku(np.array(CLOSE), 2, 3, 5)


def test_adj_close_stands_in_for_close() -> None:
    adjusted = pyta.ichimoku({"high": HIGH, "low": LOW, "adj_close": CLOSE}, 2, 3, 5)
    plain = pyta.ichimoku(small(), 2, 3, 5)

    for name in NAMES:
        np.testing.assert_array_equal(adjusted[name], plain[name])


def test_unnamed_input_takes_high_low_close_in_either_orientation() -> None:
    rows = np.column_stack([HIGH, LOW, CLOSE])

    by_rows = pyta.ichimoku(rows, 2, 3, 5)
    by_columns = pyta.ichimoku(rows.T, 2, 3, 5)

    assert isinstance(by_rows, tuple)
    assert len(by_rows) == 5
    for a, b in zip(by_rows, by_columns, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(by_rows[0][1:], TENKAN_2)
    np.testing.assert_array_equal(by_rows[4], CLOSE)


def test_columns_override_assigns_names_by_role() -> None:
    with pytest.raises(ValueError, match="column 'Hi' is not a recognized column name"):
        pyta.ichimoku(
            {"Hi": HIGH, "low": LOW, "close": CLOSE}, 2, 3, 5, columns=["Hi", "low", "close"]
        )

    result = pyta.ichimoku(
        {"h": HIGH, "l": LOW, "c": CLOSE}, 2, 3, 5, columns=["close", "low", "high"]
    )
    assert result["ichimoku_kijun"][2:] == KIJUN_3
    assert result["ichimoku_chikou"] == CLOSE


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (("high", "low", "close"), tuple(NAMES)),
        (("HIGH", "LOW", "CLOSE"), tuple(name.upper() for name in NAMES)),
        (
            ("High", "Low", "Close"),
            (
                "Ichimoku_Tenkan",
                "Ichimoku_Kijun",
                "Ichimoku_Senkou_A",
                "Ichimoku_Senkou_B",
                "Ichimoku_Chikou",
            ),
        ),
    ],
)
def test_output_names_follow_the_input_casing(
    columns: tuple[str, str, str], expected: tuple[str, ...]
) -> None:
    result = pyta.ichimoku(dict(zip(columns, (HIGH, LOW, CLOSE), strict=True)), 2, 3, 5)

    assert tuple(result) == expected


def test_json_records_give_five_keys_per_record() -> None:
    records = json.dumps(
        [{"high": h, "low": lo, "close": c} for h, lo, c in zip(HIGH, LOW, CLOSE, strict=True)]
    )

    result = json.loads(pyta.ichimoku(records, 2, 3, 5))

    assert len(result) == len(HIGH)
    assert result[2] == {
        "ichimoku_tenkan": 11.5,
        "ichimoku_kijun": 11.0,
        "ichimoku_senkou_a": 11.25,
        "ichimoku_senkou_b": None,
        "ichimoku_chikou": 12.0,
    }


@pytest.mark.pandas
def test_dataframe_gains_five_columns_with_the_index_kept(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.date_range("2024-01-01", periods=len(ohlcv.high), freq="D")
    frame = pd.DataFrame(
        {"Open": ohlcv.open, "High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close},
        index=index,
    )

    result = pyta.ichimoku(frame)

    assert list(result.columns) == [
        "Ichimoku_Tenkan",
        "Ichimoku_Kijun",
        "Ichimoku_Senkou_A",
        "Ichimoku_Senkou_B",
        "Ichimoku_Chikou",
    ]
    assert result.index.equals(index)
    np.testing.assert_array_equal(result["Ichimoku_Chikou"].to_numpy(), ohlcv.close)
    # Shifting the unshifted output with pandas: spans ahead, chikou back.
    ahead = result["Ichimoku_Senkou_A"].shift(26)
    assert ahead.iloc[26 + 25] == result["Ichimoku_Senkou_A"].iloc[25]
    assert result["Ichimoku_Chikou"].shift(-26).iloc[0] == ohlcv.close[26]


def test_output_converts_to_another_container(ohlcv: Ohlcv) -> None:
    result = json.loads(pyta.ichimoku(ohlcv.columns(), output="json"))

    assert list(result) == NAMES
    assert (
        result["ichimoku_senkou_b"][51] == pyta.ichimoku(ohlcv.columns())["ichimoku_senkou_b"][51]
    )


def test_lines_can_be_chained(ohlcv: Ohlcv) -> None:
    kijun = pyta.ichimoku(ohlcv.columns())["ichimoku_kijun"]

    smoothed = pyta.sma(kijun, period=5)

    assert np.isnan(smoothed[:29]).all()
    assert np.isfinite(smoothed[29:]).all()


def test_chained_inputs_are_aligned_on_the_longest_warm_up(ohlcv: Ohlcv) -> None:
    gapped = {"high": ohlcv.high.copy(), "low": ohlcv.low.copy(), "close": ohlcv.close.copy()}
    gapped["high"][:4] = np.nan
    gapped["close"][:9] = np.nan

    result = pyta.ichimoku(gapped)
    trimmed = pyta.ichimoku({name: values[9:] for name, values in gapped.items()})

    for name in NAMES:
        assert np.isnan(result[name][:9]).all()
        np.testing.assert_array_equal(result[name][9:], trimmed[name])


# --- shift=True ---------------------------------------------------------------------------


def test_shift_moves_the_spans_forward_and_the_chikou_back_by_kijun() -> None:
    # kijun 3: senkou A (from row 2) lands from row 5, senkou B (from row 4)
    # from row 7; the chikou span holds close three rows later.
    result = pyta.ichimoku(small(), tenkan=2, kijun=3, senkou=5, shift=True)

    assert list(result) == NAMES
    assert np.isnan(result["ichimoku_tenkan"][:1]).all()
    assert result["ichimoku_tenkan"][1:] == TENKAN_2
    assert result["ichimoku_kijun"][2:] == KIJUN_3
    assert np.isnan(result["ichimoku_senkou_a"][:5]).all()
    assert result["ichimoku_senkou_a"][5:] == SENKOU_A[:3]
    assert np.isnan(result["ichimoku_senkou_b"][:7]).all()
    assert result["ichimoku_senkou_b"][7:] == SENKOU_5[:1]
    assert result["ichimoku_chikou"][:5] == CLOSE[3:]
    assert np.isnan(result["ichimoku_chikou"][5:]).all()


@pytest.mark.pandas
@pytest.mark.parametrize(("tenkan", "kijun", "senkou"), [(9, 26, 52), (30, 5, 2), (1, 1, 1)])
def test_shift_equals_pandas_shift_of_the_unshifted_lines(
    ohlcv: Ohlcv, tenkan: int, kijun: int, senkou: int
) -> None:
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({"high": ohlcv.high, "low": ohlcv.low, "close": ohlcv.close})

    plain = pyta.ichimoku(frame, tenkan, kijun, senkou)
    shifted = pyta.ichimoku(frame, tenkan, kijun, senkou, shift=True)

    assert list(shifted.columns) == NAMES
    assert shifted.index.equals(frame.index)
    offsets = {"ichimoku_senkou_a": kijun, "ichimoku_senkou_b": kijun, "ichimoku_chikou": -kijun}
    for name in NAMES:
        expected = plain[name].shift(offsets.get(name, 0))
        np.testing.assert_array_equal(shifted[name].to_numpy(), expected.to_numpy())


def test_shift_false_is_the_default(ohlcv: Ohlcv) -> None:
    default = pyta.ichimoku(ohlcv.columns())
    explicit = pyta.ichimoku(ohlcv.columns(), shift=False)

    for name in NAMES:
        np.testing.assert_array_equal(default[name], explicit[name])


def test_shift_by_the_whole_length_leaves_the_moved_lines_empty() -> None:
    # kijun 8 on 8 rows is valid, but every moved value falls off the end.
    result = pyta.ichimoku(small(), tenkan=2, kijun=8, senkou=3, shift=True)
    plain = pyta.ichimoku(small(), tenkan=2, kijun=8, senkou=3)

    np.testing.assert_array_equal(result["ichimoku_tenkan"], plain["ichimoku_tenkan"])
    np.testing.assert_array_equal(result["ichimoku_kijun"], plain["ichimoku_kijun"])
    for name in NAMES[2:]:
        assert len(result[name]) == len(CLOSE)
        assert np.isnan(result[name]).all()


def test_shift_accepts_a_numpy_bool(ohlcv: Ohlcv) -> None:
    flagged = pyta.ichimoku(ohlcv.columns(), shift=np.bool_(True))  # type: ignore[arg-type]
    shifted = pyta.ichimoku(ohlcv.columns(), shift=True)

    for name in NAMES:
        np.testing.assert_array_equal(flagged[name], shifted[name])


@pytest.mark.parametrize("value", [1, 0, "yes", None, 1.0])
def test_shift_must_be_a_bool(value: object) -> None:
    with pytest.raises(TypeError, match="shift must be True or False, got"):
        pyta.ichimoku(small(), 2, 3, 5, shift=value)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="shift must be True or False, got"):
        pyta.batch.ichimoku([small()], 2, 3, 5, shift=value)  # type: ignore[arg-type]


def test_shift_round_trips_through_dict_and_json(ohlcv: Ohlcv) -> None:
    shifted = pyta.ichimoku(ohlcv.columns(), shift=True)
    records = json.dumps(
        [
            {"high": h, "low": lo, "close": c}
            for h, lo, c in zip(ohlcv.high, ohlcv.low, ohlcv.close, strict=True)
        ]
    )

    from_json = json.loads(pyta.ichimoku(records, shift=True))
    as_json = json.loads(pyta.ichimoku(ohlcv.columns(), shift=True, output="json"))

    assert isinstance(shifted, dict)
    assert len(from_json) == len(ohlcv.close)
    for name in NAMES:
        expected = [None if np.isnan(value) else value for value in shifted[name]]
        assert [record[name] for record in from_json] == expected
        assert as_json[name] == expected
    assert from_json[0]["ichimoku_senkou_a"] is None
    assert from_json[0]["ichimoku_chikou"] == ohlcv.close[26]
    assert from_json[-1]["ichimoku_chikou"] is None


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets = [ohlcv.columns(), small(), {"high": LOW, "low": HIGH, "close": CLOSE}]

    results = pyta.batch.ichimoku(datasets)

    single = pyta.ichimoku(ohlcv.columns())
    for name in NAMES:
        np.testing.assert_array_equal(results[0][name], single[name])
    assert isinstance(results[1], ValueError)
    assert "at least 52 values are required, got 8" in str(results[1])
    assert isinstance(results[2], ValueError)


def test_batch_mapping_keeps_keys_and_order(ohlcv: Ohlcv) -> None:
    results = pyta.batch.trend.ichimoku({"b": small(), "a": ohlcv.columns()}, 2, 3, 5)

    assert list(results) == ["b", "a"]
    assert results["b"]["ichimoku_senkou_b"][4:] == SENKOU_5


def test_batch_unnamed_datasets_give_tuples() -> None:
    results = pyta.batch.ichimoku([np.column_stack([HIGH, LOW, CLOSE])], 2, 3, 5)

    assert isinstance(results[0], tuple)
    np.testing.assert_array_equal(results[0][2][2:], SENKOU_A)


def test_batch_shared_parameters_raise_for_the_whole_call(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="kijun must be between 1 and"):
        pyta.batch.ichimoku([ohlcv.columns()], kijun=0)
    with pytest.raises(TypeError, match="senkou must be an integer"):
        pyta.batch.ichimoku([ohlcv.columns()], senkou=5.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="column= is for single-column indicators; ichimoku uses"):
        pyta.batch.ichimoku([ohlcv.columns()], column="close")  # type: ignore[arg-type]


def test_batch_shift_is_shared_and_matches_single_calls(ohlcv: Ohlcv) -> None:
    results = pyta.batch.ichimoku({"spy": ohlcv.columns(), "small": small()}, 2, 3, 5, shift=True)

    for key, data in [("spy", ohlcv.columns()), ("small", small())]:
        single = pyta.ichimoku(data, 2, 3, 5, shift=True)
        for name in NAMES:
            np.testing.assert_array_equal(results[key][name], single[name])
    assert np.isnan(results["small"]["ichimoku_senkou_a"][:5]).all()
