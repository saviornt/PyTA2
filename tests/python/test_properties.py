"""Property tests (Hypothesis) for containers, the NaN policy and multi-output results."""

import json

import numpy as np
import pyta
from hypothesis import given
from hypothesis import strategies as st

PRICE = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)


@st.composite
def series_and_period(draw: st.DrawFn, min_size: int = 1) -> tuple[list[float], int]:
    values = draw(st.lists(PRICE, min_size=min_size, max_size=200))
    period = draw(st.integers(min_value=1, max_value=len(values)))
    return values, period


@given(series_and_period())
def test_output_has_the_input_length_and_exact_warm_up(case: tuple[list[float], int]) -> None:
    values, period = case

    result = pyta.sma(np.array(values), period=period)

    assert result.shape == (len(values),)
    assert np.isnan(result[: period - 1]).all()
    assert np.isfinite(result[period - 1 :]).all()


@given(series_and_period(), st.integers(min_value=0, max_value=50))
def test_leading_nan_is_skipped_and_restored(case: tuple[list[float], int], gap: int) -> None:
    values, period = case
    padded = np.concatenate([np.full(gap, np.nan), values])

    result = pyta.sma(padded, period=period)

    assert result.shape == padded.shape
    assert np.isnan(result[: gap + period - 1]).all()
    np.testing.assert_array_equal(result[gap:], pyta.sma(np.array(values), period=period))


@given(series_and_period(), st.sampled_from(["list", "tuple", "ndarray", "dict", "json", "csv"]))
def test_container_type_is_preserved(case: tuple[list[float], int], kind: str) -> None:
    values, period = case
    data: object = {
        "list": values,
        "tuple": tuple(values),
        "ndarray": np.array(values),
        "dict": {"close": values},
        "json": "[" + ",".join(repr(value) for value in values) + "]",
        "csv": "close\n" + "\n".join(repr(value) for value in values),
    }[kind]

    result = pyta.sma(data, period=period)

    assert type(result) is type(data)


def csv_values(text: str) -> np.ndarray:
    """The one column of a CSV result, empty fields as NaN."""
    return np.array([float(field) if field else np.nan for field in text.split("\n")[1:-1]])


@given(
    series_and_period(),
    st.sampled_from(["\n", "\r\n"]),
    st.sampled_from(["", " ", "\t"]),
    st.integers(min_value=0, max_value=5),
)
def test_csv_and_numeric_strings_give_the_values_of_the_array_call(
    case: tuple[list[float], int], newline: str, pad: str, gap: int
) -> None:
    values, period = case
    want = pyta.sma(np.concatenate([np.full(gap, np.nan), values]), period=period)
    fields = [""] * gap + [f"{pad}{value!r}{pad}" for value in values]

    text = pyta.sma(
        newline.join(["Date,Close", *(f"d{i},{f}" for i, f in enumerate(fields))]), period
    )
    strings = pyta.sma(fields, period=period)

    assert text.split("\n")[0] == "SMA"
    np.testing.assert_array_equal(csv_values(text), want)
    np.testing.assert_array_equal(np.array(strings), want)
    # CSV out reads back in: the one-column result chains.
    np.testing.assert_array_equal(csv_values(pyta.sma(text, 1)), want)


@given(series_and_period(min_size=2))
def test_rsi_stays_between_zero_and_one_hundred(case: tuple[list[float], int]) -> None:
    values, period = case
    period = min(period, len(values) - 1)

    result = pyta.rsi(np.array(values), period=period)

    assert np.isnan(result[:period]).all()
    assert ((result[period:] >= 0.0) & (result[period:] <= 100.0)).all()


@given(st.lists(series_and_period(), min_size=1, max_size=8))
def test_batch_matches_single_calls(cases: list[tuple[list[float], int]]) -> None:
    period = min(p for _, p in cases)
    datasets = [np.array(values) for values, _ in cases]

    results = pyta.batch.sma(datasets, period=period)

    for dataset, result in zip(datasets, results, strict=True):
        np.testing.assert_array_equal(result, pyta.sma(dataset, period=period))


@st.composite
def macd_case(draw: st.DrawFn) -> tuple[list[float], int, int, int]:
    """A series with MACD parameters that fit it (at least `slow + signal - 1` values)."""
    fast = draw(st.integers(min_value=2, max_value=20))
    slow = draw(st.integers(min_value=2, max_value=30))
    signal = draw(st.integers(min_value=1, max_value=10))
    size = draw(st.integers(min_value=max(fast, slow) + signal - 1, max_value=120))
    values = draw(st.lists(PRICE, min_size=size, max_size=size))
    return values, fast, slow, signal


@given(macd_case())
def test_macd_hist_is_macd_minus_signal_and_lengths_match(
    case: tuple[list[float], int, int, int],
) -> None:
    values, fast, slow, signal = case

    line, sig, hist = pyta.macd(np.array(values), fast, slow, signal)

    for output in (line, sig, hist):
        assert output.shape == (len(values),)
    np.testing.assert_array_equal(hist, line - sig)
    longer = max(fast, slow)
    assert np.isnan(line[: longer - 1]).all()
    assert np.isfinite(line[longer - 1 :]).all()
    assert np.isfinite(sig[longer + signal - 2 :]).all()


@given(macd_case(), st.sampled_from(["list", "tuple", "dict", "json", "records"]))
def test_macd_results_do_not_depend_on_the_container(
    case: tuple[list[float], int, int, int], kind: str
) -> None:
    values, fast, slow, signal = case
    want = pyta.macd(np.array(values), fast, slow, signal)
    names = ["macd", "macd_signal", "macd_hist"]

    data: object = {
        "list": values,
        "tuple": tuple(values),
        "dict": {"close": values},
        "json": json.dumps(values),
        "records": json.dumps([{"close": value} for value in values]),
    }[kind]
    result = pyta.macd(data, fast, slow, signal)

    if kind in ("list", "tuple"):
        got = [np.array(output, dtype=np.float64) for output in result]
    elif kind == "dict":
        got = [np.array(result[name]) for name in names]
    else:
        parsed = json.loads(result)
        if kind == "records":
            parsed = {name: [row[name] for row in parsed] for name in names}
        got = [np.array(parsed[name], dtype=np.float64) for name in names]

    for got_one, want_one in zip(got, want, strict=True):
        np.testing.assert_array_equal(got_one, want_one)
