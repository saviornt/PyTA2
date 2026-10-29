"""Container handling and validation in the public Python API."""

import json

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv, rolling_mean

# Small hand-checked series, for tests about one specific value or dtype.
PRICES = [10.0, 11.0, 12.0, 13.0, 12.0, 14.0]
SMA_3 = np.array([np.nan, np.nan, 11.0, 12.0, 37.0 / 3.0, 13.0])

# Container tests run on the real OHLCV fixture with this period.
PERIOD = 20


def assert_series(actual: object, expected: np.ndarray = SMA_3) -> None:
    np.testing.assert_allclose(np.asarray(actual, dtype=np.float64), expected, equal_nan=True)


def assert_real_sma(actual: object, values: np.ndarray, period: int = PERIOD) -> None:
    """`actual` is the SMA of `values`, compared with an independent rolling mean."""
    expected = rolling_mean(np.asarray(values, dtype=np.float64), period)
    np.testing.assert_allclose(
        np.asarray(actual, dtype=np.float64), expected, rtol=1e-12, equal_nan=True
    )


# --- containers -----------------------------------------------------------------------------


def test_list_and_tuple_return_the_same_container(ohlcv: Ohlcv) -> None:
    closes = ohlcv.close.tolist()

    as_list = pyta.sma(closes, period=PERIOD)
    as_tuple = pyta.sma(tuple(closes), period=PERIOD)

    assert type(as_list) is list
    assert type(as_tuple) is tuple
    assert_real_sma(as_list, ohlcv.close)
    assert_real_sma(as_tuple, ohlcv.close)


@pytest.mark.parametrize("dtype", [np.float64, np.float32, np.int64, np.int32, np.uint8])
def test_ndarray_of_any_numeric_dtype(dtype: type) -> None:
    result = pyta.sma(np.array(PRICES, dtype=dtype), period=3)

    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float64
    assert_series(result)


def test_non_contiguous_and_read_only_arrays(ohlcv: Ohlcv) -> None:
    # The close column of a row-major OHLCV matrix: a strided view.
    matrix = np.column_stack(list(ohlcv.columns().values()))
    strided = matrix[:, 3]
    assert not strided.flags.c_contiguous
    assert not ohlcv.close.flags.writeable

    assert_real_sma(pyta.sma(strided, period=PERIOD), ohlcv.close)
    assert_real_sma(pyta.sma(ohlcv.close, period=PERIOD), ohlcv.close)


@pytest.mark.pandas
def test_series_keeps_index_and_is_named_after_the_indicator(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.DatetimeIndex(ohlcv.dates, name="date")

    result = pyta.sma(pd.Series(ohlcv.close, index=index, name="close"), period=PERIOD)

    assert isinstance(result, pd.Series)
    assert result.index.equals(index)
    assert result.name == "sma"
    assert_real_sma(result, ohlcv.close)


@pytest.mark.pandas
def test_series_with_nullable_dtype_treats_na_as_a_gap(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")

    result = pyta.sma(pd.Series([None, *ohlcv.close], dtype="Float64"), period=PERIOD)

    assert np.isnan(result.iloc[0])
    assert_real_sma(result.iloc[1:], ohlcv.close)


@pytest.mark.pandas
def test_dataframe_returns_a_dataframe_with_the_indicator_column(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.DatetimeIndex(ohlcv.dates, name="date")
    # Column names as a data provider might spell them.
    frame = pd.DataFrame(
        {
            "Open": ohlcv.open,
            "High": ohlcv.high,
            "Low": ohlcv.low,
            " Close ": ohlcv.close,
            "Volume": ohlcv.volume,
        },
        index=index,
    )
    name = "SMA"

    result = pyta.sma(frame, period=PERIOD)

    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == [name]
    assert result.index.equals(index)
    assert_real_sma(result[name], ohlcv.close)

    chosen = pyta.sma(frame, period=PERIOD, column="open")
    assert_real_sma(chosen[name], ohlcv.open)


@pytest.mark.pandas
def test_dataframe_column_selection_errors() -> None:
    pd = pytest.importorskip("pandas")

    assert_series(pyta.sma(pd.DataFrame({"price": PRICES}), period=3)["sma"])

    with pytest.raises(ValueError, match="available"):
        pyta.sma(pd.DataFrame({"a": PRICES, "b": PRICES}), period=3)

    with pytest.raises(ValueError, match="not found"):
        pyta.sma(pd.DataFrame({"a": PRICES}), period=3, column="close")

    with pytest.raises(ValueError, match="same after"):
        pyta.sma(pd.DataFrame({"Close": PRICES, "close ": PRICES}), period=3)


def test_dict_returns_a_dict_with_the_indicator_key(ohlcv: Ohlcv) -> None:
    # A dict of lists with a non-numeric date column, as from a CSV reader.
    data = {"date": ohlcv.dates, **ohlcv.lists()}
    name = "sma"

    result = pyta.sma(data, period=PERIOD)

    assert list(result) == [name]
    assert type(result[name]) is list
    assert_real_sma(result[name], ohlcv.close)

    arrays = pyta.sma(ohlcv.columns(), period=PERIOD)
    assert isinstance(arrays[name], np.ndarray)
    assert_real_sma(arrays[name], ohlcv.close)


def test_json_array_round_trip(ohlcv: Ohlcv) -> None:
    text = json.dumps(ohlcv.close.tolist())

    result = pyta.sma(text, period=PERIOD)

    assert isinstance(result, str)
    assert json.loads(result)[: PERIOD - 1] == [None] * (PERIOD - 1)
    assert_real_sma([np.nan if v is None else v for v in json.loads(result)], ohlcv.close)

    as_bytes = pyta.sma(text.encode(), period=PERIOD)
    assert isinstance(as_bytes, bytes)
    assert json.loads(as_bytes) == json.loads(result)


def nulls_to_nan(values: list[float | None]) -> list[float]:
    return [np.nan if value is None else value for value in values]


def test_json_columns_and_records(ohlcv: Ohlcv) -> None:
    name = "sma"
    columns = json.dumps({"date": ohlcv.dates, **ohlcv.lists()})
    assert_real_sma(nulls_to_nan(json.loads(pyta.sma(columns, period=PERIOD))[name]), ohlcv.close)

    # An array of records, one per session, as many REST APIs return.
    records = [
        {"date": date, **dict(zip(ohlcv.lists(), row, strict=True))}
        for date, row in zip(ohlcv.dates, zip(*ohlcv.lists().values(), strict=True), strict=True)
    ]
    result = json.loads(pyta.sma(json.dumps(records), period=PERIOD, column="high"))
    assert len(result) == len(records)
    assert_real_sma(nulls_to_nan([row[name] for row in result]), ohlcv.high)


def test_json_null_is_a_gap(ohlcv: Ohlcv) -> None:
    text = json.dumps([None, None, *ohlcv.close.tolist()])

    result = json.loads(pyta.sma(text, period=PERIOD))

    assert result[:2] == [None, None]
    assert_real_sma(nulls_to_nan(result[2:]), ohlcv.close)


# --- NaN policy -----------------------------------------------------------------------------


def test_leading_nans_are_skipped_and_padded() -> None:
    result = pyta.sma(np.array([np.nan, np.nan, *PRICES]), period=3)

    assert_series(result, np.concatenate([[np.nan, np.nan], SMA_3]))


def test_interior_nan_is_rejected_with_its_absolute_index() -> None:
    with pytest.raises(ValueError, match="index 3"):
        pyta.sma(np.array([np.nan, 10.0, 11.0, np.nan, 13.0, 14.0]), period=2)

    with pytest.raises(ValueError, match="index 3"):
        pyta.sma(np.array([10.0, 11.0, 12.0, np.nan, 13.0, 14.0]), period=2)


def test_infinity_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        pyta.sma(np.array([np.inf, 10.0, 11.0]), period=2)


def test_values_at_the_magnitude_limit_are_accepted() -> None:
    limit = 1e290

    np.testing.assert_array_equal(pyta.sma([limit, limit, -limit], period=2), [np.nan, limit, 0.0])
    np.testing.assert_array_equal(pyta.rsi([limit, -limit, limit], period=1), [np.nan, 0.0, 100.0])


JUST_ABOVE_LIMIT = float(np.nextafter(1e290, np.inf))


@pytest.mark.parametrize("value", [JUST_ABOVE_LIMIT, -JUST_ABOVE_LIMIT, -np.finfo(np.float64).max])
def test_values_beyond_the_magnitude_limit_are_rejected(value: float) -> None:
    with pytest.raises(ValueError, match=r"index 1 is too large.* -1e290 and 1e290"):
        pyta.sma([1.0, value, 3.0], period=2)

    # After a skipped leading NaN run the index is still absolute.
    with pytest.raises(ValueError, match=r"index 2 is too large.* -1e290 and 1e290"):
        pyta.rsi(np.array([np.nan, 1.0, value, 3.0]), period=1)

    results = pyta.batch.sma([[1.0, 2.0], [value, 2.0]], period=2)
    assert isinstance(results[1], ValueError)
    assert_series(results[0], np.array([np.nan, 1.5]))


def test_indicators_can_be_chained() -> None:
    prices = 100.0 + np.sin(np.arange(60) / 3.0)

    result = pyta.sma(pyta.rsi(prices, period=14), period=5)

    assert np.isnan(result[:18]).all()
    assert np.isfinite(result[18:]).all()


def test_all_nan_and_empty_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="no valid values"):
        pyta.sma([np.nan] * 4, period=2)

    with pytest.raises(ValueError, match="empty"):
        pyta.sma([], period=2)


# --- invalid inputs and parameters ----------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "error"),
    [
        (["a", "b", "c"], TypeError),
        ([True, False, True], TypeError),
        (np.array(["a", "b", "c"]), TypeError),
        (np.array([1 + 2j, 3 + 4j, 5 + 6j]), TypeError),
        (np.ones((3, 3)), ValueError),
        ([[1.0, 2.0], [3.0, 4.0]], ValueError),
        (42, TypeError),
        (None, TypeError),
        (range(5), TypeError),
        ("not json", ValueError),  # CSV with a header and no rows
        ("{not json", ValueError),
        ("42", ValueError),  # CSV with no header row
        ('{"close": 5}', TypeError),
        ('{"open": [1, 2, 3], "high": [1, 2, 3]}', ValueError),
    ],
)
def test_invalid_inputs(data: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        pyta.sma(data, period=2)


@pytest.mark.parametrize(
    ("period", "error"),
    [
        (0, ValueError),
        (-3, ValueError),
        (2**40, ValueError),
        (True, TypeError),
        (2.5, TypeError),
        ("3", TypeError),
        (None, TypeError),
    ],
)
def test_invalid_periods(period: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        pyta.sma(PRICES, period=period)


def test_numpy_integer_periods_are_accepted() -> None:
    assert_series(pyta.sma(PRICES, period=np.int64(3)))


def test_period_larger_than_the_series_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        pyta.sma([1.0, 2.0, 3.0], period=5)


@pytest.mark.parametrize("period", [0, -1, 2**31])
def test_out_of_range_period_message_is_one_line(period: int) -> None:
    with pytest.raises(ValueError, match=r"^period must be between 1 and \d+, got -?\d+$"):
        pyta.sma(PRICES, period=period)


def test_rsi_names_the_values_it_needs() -> None:
    with pytest.raises(ValueError, match="at least 6 values"):
        pyta.rsi([1.0, 2.0, 3.0], period=5)


def test_errors_never_leak_library_internals() -> None:
    with pytest.raises(TypeError, match="mixes records and numbers"):
        pyta.sma('[{"close": 1.0}, 2.0]', period=1)

    with pytest.raises(ValueError, match=r"nested sequences$"):
        pyta.sma([1.0, [2.0, 3.0]], period=1)


def test_column_is_rejected_for_inputs_without_columns() -> None:
    with pytest.raises(ValueError, match="column"):
        pyta.sma(PRICES, period=3, column="close")

    with pytest.raises(TypeError, match="column"):
        pyta.sma({"close": PRICES}, period=3, column=3)


def test_rsi_defaults_to_period_14() -> None:
    result = pyta.rsi(np.linspace(1.0, 20.0, 20))

    assert result.shape == (20,)
    assert np.isnan(result[:14]).all()
    assert np.isfinite(result[14:]).all()


# --- numbers as strings (one parser for every container) ------------------------------------

TEXT = ["", " NaN", "10", "11.0", " 12 ", "1.3e1", "12", "14"]
TEXT_SMA_3 = np.array([np.nan, np.nan, np.nan, np.nan, 11.0, 12.0, 37.0 / 3.0, 13.0])


def first_output(result: object) -> object:
    """The SMA values of any container's result, JSON decoded."""
    if isinstance(result, str | bytes):
        result = json.loads(result)
        if isinstance(result, list) and result and isinstance(result[0], dict):
            result = [row["sma"] for row in result]
    if isinstance(result, dict):
        result = next(iter(result.values()))
    if isinstance(result, list):
        result = nulls_to_nan(result)
    return result


@pytest.mark.parametrize(
    "data",
    [
        TEXT,
        tuple(TEXT),
        np.array(TEXT),
        [None, None, "10", 11.0, " 12 ", "1.3e1", 12, "14"],  # mixed with numbers and gaps
        {"close": TEXT},
        {"close": tuple(TEXT)},
        {"close": np.array(TEXT)},
        json.dumps(TEXT),
        json.dumps({"Close": TEXT}).encode(),
        json.dumps([{"date": i, "close": value} for i, value in enumerate(TEXT)]),
        json.dumps([None, "NaN", "10", 11, "12", 13, "12", "14"]),
    ],
    ids=lambda data: type(data).__name__,
)
def test_numbers_as_strings_are_read_in_every_container(data: object) -> None:
    assert_series(first_output(pyta.sma(data, period=3)), TEXT_SMA_3)


def test_numbers_as_strings_keep_the_container() -> None:
    assert pyta.sma(["1", "3"], period=2)[1] == 2.0
    assert type(pyta.sma(("1", "3"), period=2)) is tuple
    assert pyta.sma({"close": ("1", "3")}, period=2)["sma"][1] == 2.0


@pytest.mark.pandas
@pytest.mark.parametrize("dtype", [object, "string", "str"])
def test_pandas_string_columns_are_read(ohlcv: Ohlcv, dtype: object) -> None:
    pd = pytest.importorskip("pandas")
    text: list[str | None] = [repr(value) for value in ohlcv.close.tolist()]
    text[0] = None  # a gap: None in object, pd.NA in "string", NaN in "str"

    frame = pd.DataFrame({"Close": pd.Series(text, dtype=dtype)})
    expected = pyta.sma(np.concatenate([[np.nan], ohlcv.close[1:]]), PERIOD)

    result = pyta.sma(frame, PERIOD)

    assert list(result.columns) == ["SMA"]
    np.testing.assert_array_equal(result["SMA"].to_numpy(), expected)
    np.testing.assert_array_equal(pyta.sma(frame["Close"], PERIOD).to_numpy(), expected)


@pytest.mark.pandas
def test_pandas_object_column_of_numbers_is_read() -> None:
    pd = pytest.importorskip("pandas")

    result = pyta.sma(pd.Series([10, 11.0, "12"], dtype=object), 3)

    assert result.tolist()[2] == 11.0


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (["1", "abc"], r"^input value 'abc' at index 1 is not a number; expected a number"),
        (np.array(["1", "x"]), r"^input value 'x' at index 1 is not a number"),
        ({"Close": ["1", "2", "abc"]}, r"^column 'Close' value 'abc' at index 2 is not a number"),
        ('{"close": ["1", "abc"]}', r"^column 'close' value 'abc' at index 1"),
        ('[{"close": "1"}, {"close": "1,5"}]', r"^column 'close' value '1,5' at index 1"),
        (["1", True], r"value 'True' at index 1 is not a number"),
        ([None, "1", True], r"value True at index 2 is not a number; booleans are not numbers"),
        ([None, 1.0, {2.0}], r"value \{2.0\} at index 2 is not a number; expected a number, got"),
        (["1", "x" * 60], r"value 'xxxxxxxxx.*\.\.\. at index 1"),
        ([True, False, True], r"^input holds booleans, which are not numbers"),
        ({"close": np.array([True, False])}, r"^column 'close' holds booleans"),
        (np.array([1 + 2j]), r"^input holds complex numbers \(complex128\), which are not real"),
        (np.array(["2024-01-02"], dtype="datetime64[D]"), r"^input holds dates"),
    ],
)
def test_text_that_is_not_a_number_names_column_and_index(data: object, message: str) -> None:
    with pytest.raises(TypeError, match=message):
        pyta.sma(data, period=1)


def test_errors_never_mention_numpy_dtype_codes() -> None:
    with pytest.raises(TypeError) as caught:
        pyta.sma(["abcdef", "1"], period=1)

    assert "<U" not in str(caught.value)
    assert "dtype" not in str(caught.value)


def test_a_bool_among_numbers_in_a_list_is_read_as_one_or_zero() -> None:
    # Documented limitation (API.md §4): NumPy converts [1, True] to numbers.
    assert pyta.sma([1.0, True, False], period=1) == [1.0, 1.0, 0.0]
    assert pyta.sma("[1.0, true, false]", period=1) == "[1.0,1.0,0.0]"


@pytest.mark.pandas
@pytest.mark.parametrize(
    ("values", "dtype", "message"),
    [
        (["1", "abc"], object, r"^column 'close' value 'abc' at index 1 is not a number"),
        (["1", True], object, r"value True at index 1 is not a number; booleans"),
        ([True, False], bool, r"^column 'close' holds booleans, which are not real numbers"),
        ([True, None], "boolean", r"holds booleans"),
        (["2024-01-02"], "datetime64[ns]", r"holds dtype datetime64\[ns\]"),
    ],
)
def test_pandas_columns_that_are_not_numbers_raise(
    values: list[object], dtype: object, message: str
) -> None:
    pd = pytest.importorskip("pandas")

    with pytest.raises(TypeError, match=message):
        pyta.sma(pd.DataFrame({"close": pd.Series(values, dtype=dtype)}), 1)


# --- numbered column names ("1. open", AlphaVantage's style) --------------------------------

NUMBERED = {"1. open": [1.0, 3.0], "4. close": [10.0, 30.0], "5. adjusted close": [5.0, 7.0]}


@pytest.mark.parametrize(
    ("column", "expected"),
    [(None, 20.0), ("open", 2.0), ("1. open", 2.0), ("Adj Close", 6.0), ("2. close", 20.0)],
)
def test_numbered_names_match_in_dict_and_column(column: str | None, expected: float) -> None:
    assert pyta.sma(NUMBERED, 2, column=column)["sma"][1] == expected


def test_numbered_names_match_in_json() -> None:
    rows = [dict(zip(NUMBERED, row, strict=True)) for row in zip(*NUMBERED.values(), strict=True)]

    assert pyta.sma(json.dumps(rows), 2) == '[{"sma":null},{"sma":20.0}]'
    assert pyta.sma(json.dumps(NUMBERED), 2, column="o") == '{"sma":[null,2.0]}'


@pytest.mark.pandas
def test_numbered_names_match_in_a_dataframe_and_keep_their_casing() -> None:
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({"1. Open": [1.0, 3.0], "4. Close": [10.0, 30.0]})

    result = pyta.sma(frame, 2)

    assert list(result.columns) == ["SMA"]
    assert result["SMA"].tolist()[1] == 20.0
    assert pyta.sma(frame, 2, column="open")["SMA"].tolist()[1] == 2.0


def test_numbered_and_plain_names_together_are_ambiguous() -> None:
    with pytest.raises(ValueError, match=r"'1\. open' and 'open' are the same after ignoring case"):
        pyta.sma({"1. open": [1.0], "open": [2.0]}, 1, column="open")
