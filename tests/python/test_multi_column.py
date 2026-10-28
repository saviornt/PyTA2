"""Multi-column input: role registry, containers, `columns=`, errors and batches.

CCI (high, low, close) is the subject; nothing here is specific to it beyond
its three slots, so these tests cover every multi-column indicator.
"""

import itertools
import json
from collections.abc import Iterator

import numpy as np
import pyta
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray
from ohlcv_data import Ohlcv
from pyta import _validation
from pyta._validation import Slot, register_role, role_aliases, role_names, role_of

PERIOD = 10
NAME = f"cci_{PERIOD}"


def expected(ohlcv: Ohlcv, close: NDArray[np.float64] | None = None) -> NDArray[np.float64]:
    """CCI of the fixture through the plainest input: a tuple in slot order."""
    columns = (ohlcv.high, ohlcv.low, ohlcv.close if close is None else close)
    return np.asarray(pyta.cci(columns, PERIOD))


def records(ohlcv: Ohlcv) -> list[dict[str, object]]:
    lists = ohlcv.lists()
    return [
        {"date": date, **{name: lists[name][i] for name in lists}}
        for i, date in enumerate(ohlcv.dates)
    ]


# --- role registry --------------------------------------------------------------------------


def test_no_alias_belongs_to_two_roles() -> None:
    seen: dict[str, str] = {}

    for role in role_names():
        for alias in role_aliases(role):
            assert alias not in seen, f"{alias!r} is in {seen.get(alias)!r} and {role!r}"
            seen[alias] = role

    assert seen == _validation._ROLE_OF  # pyright: ignore[reportPrivateUsage]


def test_every_alias_is_already_squashed_and_names_come_first() -> None:
    for role in role_names():
        aliases = role_aliases(role)
        assert aliases[0] == _validation.squash(role)
        assert all(alias == _validation.squash(alias) for alias in aliases)


@pytest.fixture
def scratch_role() -> Iterator[str]:
    """A test-only role, removed again afterwards so the registry is unchanged."""
    name = register_role("test_eps", "Earnings Per Share", "EPS")
    try:
        yield name
    finally:
        for alias in _validation._ROLE_ALIASES.pop(name):  # pyright: ignore[reportPrivateUsage]
            del _validation._ROLE_OF[alias]  # pyright: ignore[reportPrivateUsage]


def test_a_new_role_is_one_registration_and_is_found_by_name(scratch_role: str) -> None:
    from pyta._api import run_columns
    from pyta._native import cci

    assert role_of("earnings-per-share") == scratch_role
    assert role_of("EPS") == scratch_role
    assert scratch_role in role_names()

    # A slot can accept the new role at once: run CCI with EPS as its close.
    slots = (Slot("high", ("high",)), Slot("low", ("low",)), Slot("close", (scratch_role,)))
    data = {"High": [3.0, 6.0, 9.0], "Low": [0.0] * 3, "Earnings per share": [0.0] * 3}

    result = run_columns(cci, "test", data, 3, None, slots)

    assert result["test_3"][2] == pytest.approx(100.0)


def test_a_role_or_alias_cannot_be_registered_twice(scratch_role: str) -> None:
    with pytest.raises(ValueError, match="role 'test_eps' is already registered"):
        register_role(scratch_role)
    with pytest.raises(ValueError, match=r"'adjclose' \(adj_close\)"):
        register_role("test_other", "Adj. Close")


def test_slots_describe_the_roles_they_accept() -> None:
    assert Slot("high", ("high",)).describe() == "high"
    assert Slot("close", ("close", "adj_close")).describe() == "close (close or adj_close)"


# --- named containers -----------------------------------------------------------------------


def test_dict_of_lists_with_extra_and_non_numeric_columns(ohlcv: Ohlcv) -> None:
    data = {"date": ohlcv.dates, "symbol": ["SPY"] * 300, **ohlcv.lists()}

    result = pyta.cci(data, PERIOD)

    assert list(result) == [NAME]
    assert isinstance(result[NAME], list)
    np.testing.assert_array_equal(result[NAME], expected(ohlcv))


def test_dict_of_exactly_the_needed_arrays(ohlcv: Ohlcv) -> None:
    data = {"high": ohlcv.high, "low": ohlcv.low, "close": ohlcv.close}

    result = pyta.cci(data, PERIOD)

    assert isinstance(result[NAME], np.ndarray)
    np.testing.assert_array_equal(result[NAME], expected(ohlcv))


@pytest.mark.pandas
def test_full_dataframe_with_its_date_column_needs_no_names(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({"date": ohlcv.dates, **ohlcv.columns(), "symbol": "SPY"})

    result = pyta.cci(frame, PERIOD)

    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == [NAME]
    assert result.index.equals(frame.index)
    np.testing.assert_array_equal(result[NAME], expected(ohlcv))


@pytest.mark.pandas
def test_dataframe_with_exactly_the_needed_columns_keeps_its_index(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.DatetimeIndex(ohlcv.dates)
    frame = pd.DataFrame({"Close": ohlcv.close, "Low": ohlcv.low, "High": ohlcv.high}, index=index)

    result = pyta.cci(frame, PERIOD)

    assert result.index.equals(index)
    np.testing.assert_array_equal(result[NAME], expected(ohlcv))


@pytest.mark.pandas
def test_dict_of_series_returns_a_series(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    data = {name: pd.Series(values) for name, values in ohlcv.columns().items()}

    result = pyta.cci(data, PERIOD)

    assert isinstance(result[NAME], pd.Series)
    assert result[NAME].name == NAME
    np.testing.assert_array_equal(result[NAME], expected(ohlcv))


@pytest.mark.parametrize("as_bytes", [False, True])
def test_json_records_and_columns(ohlcv: Ohlcv, as_bytes: bool) -> None:
    by_rows = json.dumps(records(ohlcv))
    by_columns = json.dumps({"date": ohlcv.dates, **ohlcv.lists()})
    want = [None if np.isnan(v) else v for v in expected(ohlcv).tolist()]

    for text, shape in ((by_rows, "rows"), (by_columns, "columns")):
        result = pyta.cci(text.encode() if as_bytes else text, PERIOD)

        assert isinstance(result, bytes if as_bytes else str)
        parsed = json.loads(result)
        if shape == "rows":
            assert [row[NAME] for row in parsed] == want
        else:
            assert parsed == {NAME: want}


@pytest.mark.pandas
def test_provider_style_names_and_the_adjusted_close(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    adjusted = ohlcv.close * 0.98
    frame = pd.DataFrame(
        {"Date": ohlcv.dates, "High": ohlcv.high, "Low": ohlcv.low, "Adj Close": adjusted}
    )

    # Without a close column, the close slot takes the adjusted close.
    np.testing.assert_array_equal(pyta.cci(frame, PERIOD)[NAME], expected(ohlcv, adjusted))

    # With both, the close is preferred unless named.
    frame["Close"] = ohlcv.close
    np.testing.assert_array_equal(pyta.cci(frame, PERIOD)[NAME], expected(ohlcv))
    np.testing.assert_array_equal(
        pyta.cci(frame, PERIOD, columns=["High", "Low", "adjusted close"])[NAME],
        expected(ohlcv, adjusted),
    )


def test_spellings_that_differ_only_in_case_are_ambiguous_only_for_roles(ohlcv: Ohlcv) -> None:
    # Two date columns are ignored like any other unneeded column.
    data = {"Date": ohlcv.dates, "date": ohlcv.dates, **ohlcv.lists()}
    np.testing.assert_array_equal(pyta.cci(data, PERIOD)[NAME], expected(ohlcv))

    with pytest.raises(ValueError, match="column names 'high' and 'HIGH' are the same"):
        pyta.cci({**ohlcv.lists(), "HIGH": ohlcv.high}, PERIOD)


# --- the columns= override ------------------------------------------------------------------


def test_every_order_of_columns_gives_the_same_result(ohlcv: Ohlcv) -> None:
    want = expected(ohlcv)

    for order in itertools.permutations(["High", "low", "CLOSE"]):
        result = pyta.cci(ohlcv.columns(), PERIOD, columns=list(order))
        np.testing.assert_array_equal(result[NAME], want)

    np.testing.assert_array_equal(
        pyta.cci(ohlcv.columns(), PERIOD, columns=("c", "l", "h"))[NAME], want
    )


@given(st.permutations(["high", "low", "close"]))
def test_any_permutation_of_columns_gives_the_same_result(order: list[str]) -> None:
    rng = np.random.default_rng(7)
    low = 100.0 + np.cumsum(rng.uniform(-1.0, 1.0, 60))
    high = low + rng.uniform(0.0, 2.0, 60)
    close = low + (high - low) * rng.uniform(0.0, 1.0, 60)
    data = {"volume": np.ones(60), "close": close, "low": low, "high": high}

    result = pyta.cci(data, 14, columns=order)["cci_14"]

    np.testing.assert_array_equal(result, pyta.cci((high, low, close), 14))


@pytest.mark.parametrize(
    ("columns", "message"),
    [
        (["high", "low", "price"], "column 'price' is not a recognized column name"),
        (["high", "low", "volume"], r"column 'volume' \(volume\) is not an input of cci"),
        (
            ["high", "low", "close", "adj close"],
            r"columns 'close' and 'adj close' both fill cci's close \(close or adj_close\) input",
        ),
        (["high", "h", "close"], "columns 'high' and 'h' both fill cci's high input"),
        (["low", "close"], r"columns= leaves out: high"),
        ([], "columns= leaves out: high, low, close"),
        (["high", "low", "adj close"], "column 'adj close' not found; available columns: "),
    ],
)
def test_invalid_columns_raise_and_say_what_cci_needs(
    ohlcv: Ohlcv, columns: list[str], message: str
) -> None:
    with pytest.raises(ValueError, match=message) as error:
        pyta.cci(ohlcv.columns(), PERIOD, columns=columns)

    if "available" not in message:
        assert "cci needs the columns high, low and close (close or adj_close)" in str(error.value)


@pytest.mark.parametrize(
    ("columns", "message"),
    [("high", "columns must be a list of column names, got str"), (["high", 1], "only str")],
)
def test_columns_of_the_wrong_type_raise_type_error(columns: object, message: str) -> None:
    with pytest.raises(TypeError, match=message):
        pyta.cci({"high": [1.0]}, PERIOD, columns=columns)  # type: ignore[arg-type]


def test_column_and_columns_belong_to_their_own_kind_of_indicator(ohlcv: Ohlcv) -> None:
    with pytest.raises(ValueError, match="column= is for single-column indicators; cci uses"):
        pyta.cci(ohlcv.columns(), PERIOD, column="close")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="column= is for single-column"):
        pyta.batch.cci([ohlcv.columns()], PERIOD, column="close")  # type: ignore[arg-type]

    for name in ("sma", "rsi"):
        with pytest.raises(ValueError, match=f"columns= is for multi-column indicators; {name}"):
            getattr(pyta, name)(ohlcv.columns(), PERIOD, columns=["close"])
        with pytest.raises(ValueError, match="columns= is for multi-column"):
            getattr(pyta.batch, name)([ohlcv.close], PERIOD, columns=["close"])


# --- missing columns ------------------------------------------------------------------------


def test_a_missing_column_names_the_required_and_the_available_columns(ohlcv: Ohlcv) -> None:
    data = {"date": ohlcv.dates, "open": ohlcv.open, "high": ohlcv.high, "close": ohlcv.close}

    with pytest.raises(ValueError, match="missing: low") as error:
        pyta.cci(data, PERIOD)

    assert str(error.value) == (
        "cci needs the columns high, low and close (close or adj_close); missing: low. "
        "Available columns: 'date', 'open', 'high', 'close'. Rename the input's columns, "
        "or pass columns=[...] to choose them"
    )


def test_every_missing_column_is_listed() -> None:
    with pytest.raises(ValueError, match=r"missing: high, low, close \(close or adj_close\)\. "):
        pyta.cci({"volume": [1.0, 2.0]}, PERIOD)
    with pytest.raises(ValueError, match="Available columns: none"):
        pyta.cci({}, PERIOD)


# --- unnamed input --------------------------------------------------------------------------


def test_unnamed_input_takes_the_documented_order(ohlcv: Ohlcv) -> None:
    stacked = np.column_stack([ohlcv.high, ohlcv.low, ohlcv.close])

    from_array = pyta.cci(stacked, PERIOD)
    from_tuple = pyta.cci((ohlcv.high.tolist(), ohlcv.low.tolist(), ohlcv.close.tolist()), PERIOD)
    from_masked = pyta.cci(np.ma.MaskedArray(stacked), PERIOD)

    assert isinstance(from_array, np.ndarray)
    assert from_array.shape == (300,)
    assert isinstance(from_tuple, tuple)
    np.testing.assert_array_equal(from_array, expected(ohlcv))
    np.testing.assert_array_equal(np.array(from_tuple), expected(ohlcv))
    np.testing.assert_array_equal(from_masked, expected(ohlcv))


@pytest.mark.parametrize("width", [2, 4])
def test_unnamed_input_with_the_wrong_column_count(width: int) -> None:
    rows = np.ones((20, width))

    with pytest.raises(
        ValueError,
        match=f"cci takes 3 columns in the order high, low, close; the array has {width}",
    ):
        pyta.cci(rows, PERIOD)
    with pytest.raises(ValueError, match=f"the tuple has {width}"):
        pyta.cci(tuple(rows.T), PERIOD)


def test_unnamed_input_has_no_names_to_choose_from() -> None:
    with pytest.raises(ValueError, match="columns= is not valid for a 2-D array"):
        pyta.cci(np.ones((20, 3)), PERIOD, columns=["high", "low", "close"])
    with pytest.raises(ValueError, match="columns= is not valid for a tuple of arrays"):
        pyta.cci((np.ones(20),) * 3, PERIOD, columns=["high", "low", "close"])


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        ([1.0, 2.0, 3.0], "a list"),
        (np.ones(5), "a 1-D array"),
        ((1.0, 2.0, 3.0), "a tuple of numbers"),
        ((), "a tuple of numbers"),
        ("[1.0, 2.0]", "a JSON array of numbers"),
    ],
)
def test_one_series_raises_type_error_saying_several_are_needed(data: object, kind: str) -> None:
    with pytest.raises(
        TypeError,
        match=f"cci needs the columns high, low and close .*, but {kind} holds one series",
    ):
        pyta.cci(data, PERIOD)


@pytest.mark.pandas
def test_a_pandas_series_or_multiindex_frame_is_rejected() -> None:
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame(
        np.ones((5, 2)), columns=pd.MultiIndex.from_tuples([("a", "high"), ("a", "low")])
    )

    with pytest.raises(TypeError, match="a pandas Series holds one series"):
        pyta.cci(pd.Series([1.0, 2.0]), PERIOD)
    with pytest.raises(TypeError, match="MultiIndex"):
        pyta.cci(frame, PERIOD)


@pytest.mark.parametrize(
    ("data", "error", "message"),
    [
        (np.ones((2, 3, 3)), ValueError, r"expected a 2-D array of shape \(rows, columns\)"),
        (42, TypeError, "unsupported input type int"),
        ("{not json", ValueError, "invalid JSON input"),
        ('[{"high": 1.0}, 2.0]', TypeError, "mixes records and numbers"),
        (
            '{"high": 1.0, "low": [1.0], "close": [1.0]}',
            TypeError,
            "JSON column 'high' must be an array",
        ),
        ("3.5", TypeError, "JSON input must be an array of records or an object of arrays"),
        ({"high": [1.0], "low": "x", "close": [1.0]}, TypeError, "column 'low' must be a list"),
    ],
)
def test_malformed_input(data: object, error: type[Exception], message: str) -> None:
    with pytest.raises(error, match=message):
        pyta.cci(data, PERIOD)


# --- values ---------------------------------------------------------------------------------


def test_columns_of_different_lengths_raise() -> None:
    with pytest.raises(
        ValueError, match=r"columns have different lengths \('high': 3, 'low': 2, 'close': 3\)"
    ):
        pyta.cci({"high": [3.0, 3.0, 3.0], "low": [1.0, 1.0], "close": [2.0, 2.0, 2.0]}, 2)


def test_nan_after_the_leading_run_names_the_column_and_row(ohlcv: Ohlcv) -> None:
    data = ohlcv.lists()
    data["low"][0] = float("nan")  # leading: skipped
    data["low"][7] = float("nan")

    with pytest.raises(ValueError, match=r"column 'low': non-finite value .* at index 7"):
        pyta.cci(data, PERIOD)

    data["low"][7] = data["low"][6]
    data["high"][7] = 1e300
    with pytest.raises(
        ValueError, match="column 'high': value at index 7 is too large in magnitude"
    ):
        pyta.cci(data, PERIOD)


def test_an_infinite_value_in_unnamed_input_names_its_position() -> None:
    rows = np.column_stack([np.full(20, 2.0), np.ones(20), np.ones(20)])
    rows[3, 2] = np.inf

    with pytest.raises(
        ValueError, match=r"column 'column 2 \(close\)': non-finite value .* at index 3"
    ):
        pyta.cci(rows, PERIOD)


def test_no_complete_row_raises() -> None:
    nan = float("nan")

    with pytest.raises(ValueError, match="input contains no complete row"):
        pyta.cci({"high": [nan, 2.0], "low": [1.0, nan], "close": [nan, nan]}, 1)


def test_high_below_low_names_the_columns_and_the_callers_row(ohlcv: Ohlcv) -> None:
    data = {"High": ohlcv.high.copy(), "Low": ohlcv.low.copy(), "Close": ohlcv.close.copy()}
    data["Close"][:3] = np.nan  # rows are numbered as the caller's, not after the skip
    data["High"][42] = data["Low"][42] - 0.5

    with pytest.raises(ValueError, match="at index 42") as error:
        pyta.cci(data, PERIOD)

    assert str(error.value).startswith(
        "column 'High' (high) is below column 'Low' (low) at index 42 ("
    )
    assert str(error.value).endswith("); high must be at least low on every row")


def test_high_equal_to_low_is_valid() -> None:
    flat = np.full(5, 3.0)

    assert pyta.cci((flat, flat, flat), 2)[1:] == (0.0,) * 4


# --- batch ----------------------------------------------------------------------------------


def test_batch_returns_failures_in_place_and_completes_the_rest(
    ohlcv: Ohlcv, caplog: pytest.LogCaptureFixture
) -> None:
    good = ohlcv.columns()
    inverted = {"high": ohlcv.low, "low": ohlcv.high, "close": ohlcv.close}
    datasets = [
        good,
        {"open": ohlcv.open, "close": ohlcv.close},  # missing high and low
        inverted,  # high below low
        (ohlcv.high[:5], ohlcv.low[:5], ohlcv.close[:5]),  # too short: Rust's error
        [1.0, 2.0],  # one series
        np.column_stack([ohlcv.high, ohlcv.low, ohlcv.close]),
    ]

    with caplog.at_level("WARNING", logger="pyta.api"):
        results = pyta.batch.cci(datasets, PERIOD)

    assert isinstance(results, list)
    np.testing.assert_array_equal(results[0][NAME], expected(ohlcv))
    assert isinstance(results[1], ValueError)
    assert "missing: high, low" in str(results[1])
    assert isinstance(results[2], ValueError)
    assert "is below column 'low'" in str(results[2])
    assert isinstance(results[3], ValueError)
    assert "at least 10 values are required, got 5" in str(results[3])
    assert isinstance(results[4], TypeError)
    np.testing.assert_array_equal(results[5], expected(ohlcv))
    assert "cci: 4 of 6 datasets failed" in caplog.text


def test_batch_mapping_and_shared_columns_override(ohlcv: Ohlcv) -> None:
    adjusted = ohlcv.close * 0.98
    datasets = {
        "b": {**ohlcv.columns(), "adj_close": adjusted},
        "a": {"h": ohlcv.high, "l": ohlcv.low, "adjusted close": adjusted},
    }

    results = pyta.batch.momentum.cci(datasets, PERIOD, columns=["adj close", "low", "high"])

    assert list(results) == ["b", "a"]
    for result in results.values():
        np.testing.assert_array_equal(result[NAME], expected(ohlcv, adjusted))


def test_batch_validates_shared_arguments() -> None:
    with pytest.raises(TypeError, match="datasets must be a list or a mapping"):
        pyta.batch.cci((np.ones((5, 3)),), PERIOD)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="period must be between 1 and"):
        pyta.batch.cci([np.ones((5, 3))], 0)
    with pytest.raises(TypeError, match="columns must be a list of column names"):
        pyta.batch.cci([np.ones((5, 3))], PERIOD, columns="high")  # type: ignore[arg-type]

    assert pyta.batch.cci([], PERIOD) == []


def test_batch_names_the_column_of_an_invalid_value(ohlcv: Ohlcv) -> None:
    bad = ohlcv.lists()
    bad["close"][7] = float("inf")

    good, failed = pyta.batch.cci([ohlcv.columns(), bad], PERIOD)

    np.testing.assert_array_equal(good[NAME], expected(ohlcv))
    assert isinstance(failed, ValueError)
    assert str(failed).startswith("column 'close': non-finite value (NaN or infinity) at index 7")
