"""CSV input and output: detection, parsing, column selection, casing, errors and batches.

CSV text needs a header row; text whose first non-whitespace character is `[`
or `{` is JSON. Results are CSV of the output names, one row per input row,
with an empty field for NaN.
"""

import csv
import io

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

PERIOD = 20


def table(text: str | bytes) -> dict[str, NDArray[np.float64]]:
    """A CSV result read back independently: each column as floats, empty fields NaN."""
    if isinstance(text, bytes):
        text = text.decode()
    rows = list(csv.reader(io.StringIO(text, newline="")))
    header, body = rows[0], rows[1:]
    return {
        name: np.array([float(row[i]) if row and row[i] else np.nan for row in body])
        for i, name in enumerate(header)
    }


def header(text: str | bytes) -> str:
    line = text.splitlines()[0]
    return line.decode() if isinstance(line, bytes) else line


def lines(name: str, values: NDArray[np.float64]) -> str:
    """A one-column CSV of `values`, written with Python's shortest `repr`."""
    return "\n".join([name, *map(repr, values.tolist())]) + "\n"


def alphavantage(ohlcv: Ohlcv) -> str:
    """The fixture in AlphaVantage's CSV layout, newest row first as AlphaVantage sends it."""
    rows = [
        ",".join([date, *(repr(float(ohlcv.columns()[name][i])) for name in ohlcv.columns())])
        for i, date in enumerate(ohlcv.dates)
    ]
    return "\r\n".join(["timestamp,open,high,low,close,volume", *reversed(rows)]) + "\r\n"


def oldest_first(text: str) -> str:
    """The caller's reverse of newest-first CSV rows, as API.md §12 shows."""
    first, *rows = text.splitlines()
    return "\n".join([first, *reversed(rows)])


# --- detection ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["[1, 2, 3]", "  \n[1, 2, 3]", "\ufeff[1, 2, 3]", b" \t[1, 2, 3]", bytearray(b"\n[1,2,3]")],
)
def test_text_starting_with_a_bracket_is_json(text: str | bytes | bytearray) -> None:
    result = pyta.sma(text, 2)

    assert result in ("[null,1.5,2.5]", b"[null,1.5,2.5]")


def test_json_bytes_with_a_byte_order_mark_are_still_json() -> None:
    assert pyta.sma(b'\xef\xbb\xbf{"close": [1, 2, 3]}', 2) == b'{"sma":[null,1.5,2.5]}'


def test_other_text_is_csv() -> None:
    assert pyta.sma("close\n1\n2\n3\n", 2) == "sma\n\n1.5\n2.5\n"


# --- one column -----------------------------------------------------------------------------


def test_one_column_csv_matches_the_array_call(ohlcv: Ohlcv) -> None:
    result = pyta.sma(lines("close", ohlcv.close), PERIOD)

    assert type(result) is str
    np.testing.assert_array_equal(table(result)["sma"], pyta.sma(ohlcv.close, PERIOD))


@pytest.mark.parametrize("kind", [bytes, bytearray])
def test_bytes_give_bytes(ohlcv: Ohlcv, kind: type[bytes | bytearray]) -> None:
    result = pyta.sma(kind(lines("close", ohlcv.close).encode()), PERIOD)

    assert type(result) is bytes
    np.testing.assert_array_equal(table(result)["sma"], pyta.sma(ohlcv.close, PERIOD))


def test_output_format() -> None:
    # Header of output names, an empty field for NaN, shortest repr, "\n" line endings.
    expected = "sma\n\n0.15000000000000002\n0.10000005000000002\n1e-07\n"

    assert pyta.sma("close\n0.1\n0.2\n1e-7\n1e-7\n", 2) == expected


def test_a_lone_column_is_used_whatever_its_name() -> None:
    assert pyta.sma("price\n1\n2\n", 2) == "sma\n\n1.5\n"


def test_csv_results_chain() -> None:
    once = pyta.sma("close\n1\n2\n3\n4\n5\n", 2)

    assert pyta.sma(once, 2) == "sma\n\n\n2.0\n3.0\n4.0\n"


def test_multi_output_gives_one_column_per_output(ohlcv: Ohlcv) -> None:
    result = pyta.macd(lines("close", ohlcv.close), 5, 35, 5)
    expected = pyta.macd(ohlcv.close, 5, 35, 5)

    assert header(result) == "macd,macd_signal,macd_hist"
    for name, values in zip(("macd", "macd_signal", "macd_hist"), expected, strict=True):
        np.testing.assert_array_equal(table(result)[name], values)


def test_header_only_is_empty_input() -> None:
    with pytest.raises(ValueError, match="input series is empty"):
        pyta.sma("close\n", 1)


@pytest.mark.parametrize("text", ["", "   ", b"", "\ufeff", "1\n2\n3\n", " 1.5 ,,NaN\n1,2,3\n"])
def test_text_with_no_header_row_raises(text: str | bytes) -> None:
    with pytest.raises(ValueError, match="CSV input has no header row"):
        pyta.sma(text, 1)


# --- missing values -------------------------------------------------------------------------


@pytest.mark.parametrize("gap", ["", "NaN", "nan", "  ", " NaN "])
def test_empty_fields_and_nan_text_are_gaps(gap: str) -> None:
    text = f"date,close\n2024-01-01,{gap}\n2024-01-02,{gap}\n2024-01-03,1\n2024-01-04,3\n"

    assert pyta.sma(text, 2) == "sma\n\n\n\n2.0\n"


def test_blank_lines_in_a_one_column_file_are_gaps_and_trailing_ones_are_ignored() -> None:
    assert pyta.sma("close\n\n1\n3\n\n\n", 2) == "sma\n\n\n2.0\n"


def test_a_gap_after_the_first_value_raises() -> None:
    with pytest.raises(ValueError, match=r"non-finite value .* at index 1"):
        pyta.sma("close\n1\n\n3\n", 1)


# --- bad values -----------------------------------------------------------------------------


def test_text_that_is_not_a_number_names_the_column_and_row() -> None:
    with pytest.raises(TypeError, match=r"column 'close' value 'abc' at index 2 is not a number"):
        pyta.sma("date,close\nd1,1\nd2,2\nd3,abc\n", 1)


def test_unused_columns_are_never_parsed() -> None:
    assert pyta.sma("timestamp,note,close\n2024-01-02,n/a,1\nx,y,3\n", 2) == "sma\n\n2.0\n"


def test_numbers_may_have_surrounding_whitespace() -> None:
    assert pyta.sma("close\n 1 \n\t3\n 1e1\n", 2) == "sma\n\n2.0\n6.5\n"


def test_infinity_is_rejected_by_the_value_check() -> None:
    with pytest.raises(ValueError, match=r"non-finite value .* at index 1"):
        pyta.sma("close\n1\ninf\n", 1)


# --- CSV syntax -----------------------------------------------------------------------------


def test_crlf_line_endings(ohlcv: Ohlcv) -> None:
    text = lines("close", ohlcv.close).replace("\n", "\r\n")

    result = pyta.sma(text, PERIOD)

    assert "\r" not in result
    np.testing.assert_array_equal(table(result)["sma"], pyta.sma(ohlcv.close, PERIOD))


@pytest.mark.parametrize(
    "text", [b"\xef\xbb\xbfclose\n1\n3\n", "\ufeffclose\n1\n3\n"], ids=["bytes", "str"]
)
def test_byte_order_mark_is_skipped(text: str | bytes) -> None:
    result = pyta.sma(text, 2)

    assert result in ("sma\n\n2.0\n", b"sma\n\n2.0\n")


def test_quoted_fields() -> None:
    text = 'note,"Close"\n"a, b",1\n"say ""hi""\nthere","3"\n'

    assert pyta.sma(text, 2) == "SMA\n\n2.0\n"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("date,close\nd1,1\nd2\n", r"CSV row 1 .* has 1 fields, but the header has 2"),
        ("date,close\nd1,1,9\n", r"CSV row 0 .* has 3 fields, but the header has 2"),
        ("date,close\nd1,1\n\nd3,2\n", r"CSV row 1 .* has 0 fields, but the header has 2"),
    ],
)
def test_ragged_rows_raise(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        pyta.sma(text, 1)


def test_malformed_quoting_raises() -> None:
    with pytest.raises(ValueError, match="invalid CSV input"):
        pyta.sma('close\n"1"x\n', 1)


def test_invalid_utf8_raises() -> None:
    with pytest.raises(ValueError, match="CSV input is not valid UTF-8"):
        pyta.sma(b"close\n\xff\n", 1)


# --- column selection and casing ------------------------------------------------------------


def test_default_column_and_column_selection(ohlcv: Ohlcv) -> None:
    text = oldest_first(alphavantage(ohlcv))

    np.testing.assert_array_equal(table(pyta.sma(text, PERIOD))["sma"], pyta.sma(ohlcv.close, 20))
    np.testing.assert_array_equal(
        table(pyta.sma(text, PERIOD, column="opening"))["sma"], pyta.sma(ohlcv.open, PERIOD)
    )


def test_aliases_and_numbered_names_match() -> None:
    text = "1. open,5. Adjusted Close\n1,10\n3,30\n"

    assert pyta.sma(text, 2, column="adj_close") == "SMA\n\n20.0\n"
    assert pyta.sma(text, 2, column="open") == "sma\n\n2.0\n"


@pytest.mark.parametrize(
    ("column", "message"),
    [("price", "not a recognized column name"), ("volume", "column 'volume' not found")],
)
def test_bad_column_raises(column: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        pyta.sma("open,close\n1,2\n", 1, column=column)


def test_no_default_column_raises() -> None:
    with pytest.raises(ValueError, match="no 'close' column found"):
        pyta.sma("open,high\n1,2\n", 1)


def test_numbered_and_plain_spellings_of_one_name_are_ambiguous() -> None:
    with pytest.raises(ValueError, match=r"'1\. open' and 'open' are the same after ignoring"):
        pyta.sma("1. open,open\n1,2\n", 1, column="open")


@pytest.mark.parametrize(
    ("name", "expected"),
    [("close", "sma"), ("CLOSE", "SMA"), ("Close", "SMA"), ("cLoSe", "sma"), ("4. Close", "SMA")],
)
def test_output_casing_follows_the_header(name: str, expected: str) -> None:
    assert header(pyta.sma(f"{name}\n1\n", 1)) == expected


def test_title_case_header_casing_for_several_outputs() -> None:
    text = "Date,Close\n" + "".join(f"d{i},{i}\n" for i in range(1, 40))

    assert header(pyta.macd(text, 5, 35, 5)) == "MACD,MACD_Signal,MACD_Hist"


# --- AlphaVantage layout --------------------------------------------------------------------


def test_alphavantage_csv_gives_the_values_of_the_numpy_call(ohlcv: Ohlcv) -> None:
    text = oldest_first(alphavantage(ohlcv))

    np.testing.assert_array_equal(
        table(pyta.sma(text, PERIOD))["sma"], pyta.sma(ohlcv.close, PERIOD)
    )
    np.testing.assert_array_equal(
        table(pyta.cci(text, PERIOD))["cci"],
        pyta.cci((ohlcv.high, ohlcv.low, ohlcv.close), PERIOD),
    )
    macd = table(pyta.macd(text.encode(), 12, 26, 9))
    for name, values in zip(macd, pyta.macd(ohlcv.close, 12, 26, 9), strict=True):
        np.testing.assert_array_equal(macd[name], values)


def test_alphavantage_csv_newest_first_is_not_reordered(ohlcv: Ohlcv) -> None:
    result = table(pyta.sma(alphavantage(ohlcv), PERIOD))["sma"]

    np.testing.assert_array_equal(result, pyta.sma(ohlcv.close[::-1].copy(), PERIOD))


# --- multi-column indicators ----------------------------------------------------------------


def test_cci_csv_matches_the_tuple_call(ohlcv: Ohlcv) -> None:
    text = oldest_first(alphavantage(ohlcv)).encode()

    result = pyta.cci(text, PERIOD)

    assert type(result) is bytes
    assert header(result) == "cci"
    np.testing.assert_array_equal(
        table(result)["cci"], pyta.cci((ohlcv.high, ohlcv.low, ohlcv.close), PERIOD)
    )


def test_cci_csv_with_numbered_names_and_columns() -> None:
    text = "1. Open,2. High,3. Low,4. Close,5. Adjusted Close\n0,3,1,2,9\n0,4,2,3,9\n0,5,3,4,9\n"
    plain = pyta.cci(([3.0, 4.0, 5.0], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]), 2)

    result = pyta.cci(text, 2)

    assert header(result) == "CCI"
    np.testing.assert_array_equal(table(result)["CCI"], plain)

    chosen = pyta.cci(text, 2, columns=["high", "3. low", "adjusted close"])
    np.testing.assert_array_equal(
        table(chosen)["CCI"], pyta.cci(([3.0, 4.0, 5.0], [1.0, 2.0, 3.0], [9.0] * 3), 2)
    )


def test_cci_csv_high_below_low_names_the_row() -> None:
    with pytest.raises(
        ValueError, match=r"column 'High' \(high\) is below column 'Low' \(low\) at index 2"
    ):
        pyta.cci("Date,High,Low,Close\nd0,3,1,2\nd1,4,2,3\nd2,1,3,2\n", 2)


def test_cci_csv_bad_text_and_missing_column() -> None:
    with pytest.raises(TypeError, match=r"column 'low' value 'x' at index 1 is not a number"):
        pyta.cci("high,low,close,note\n3,1,2,a\n4,x,3,b\n", 2)

    with pytest.raises(ValueError, match="missing: low"):
        pyta.cci("high,close\n3,2\n", 2)


def test_cci_csv_ignores_unused_columns() -> None:
    result = pyta.cci("high,low,close,volume\n3,1,2,lots\n4,2,3,many\n5,3,4,few\n", 2)

    assert result == "cci\n\n66.66666666666667\n66.66666666666667\n"


# --- batch ----------------------------------------------------------------------------------


def test_batch_of_csv_datasets_keeps_a_bad_one_in_place(ohlcv: Ohlcv) -> None:
    good = lines("close", ohlcv.close)
    datasets = [good, "close\n1\nabc\n", good.encode(), "date,close\nd1\n"]

    results = pyta.batch.sma(datasets, PERIOD)

    np.testing.assert_array_equal(table(results[0])["sma"], pyta.sma(ohlcv.close, PERIOD))
    assert isinstance(results[1], TypeError)
    assert "value 'abc' at index 1" in str(results[1])
    assert results[2] == results[0].encode()
    assert isinstance(results[3], ValueError)
    assert "CSV row 0" in str(results[3])


def test_cci_batch_of_csv_datasets_keeps_a_bad_one_in_place(ohlcv: Ohlcv) -> None:
    good = oldest_first(alphavantage(ohlcv))
    bad = "high,low,close\n3,1,2\n1,3,2\n"

    results = pyta.batch.cci({"spy": good, "bad": bad}, PERIOD)

    assert list(results) == ["spy", "bad"]
    np.testing.assert_array_equal(
        table(results["spy"])["cci"], pyta.cci((ohlcv.high, ohlcv.low, ohlcv.close), PERIOD)
    )
    assert isinstance(results["bad"], ValueError)
    assert "at index 1" in str(results["bad"])
