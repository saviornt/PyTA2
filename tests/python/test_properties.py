"""Property tests (Hypothesis) for containers and the NaN policy."""

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


@given(series_and_period(), st.sampled_from(["list", "tuple", "ndarray", "dict", "json"]))
def test_container_type_is_preserved(case: tuple[list[float], int], kind: str) -> None:
    values, period = case
    data: object = {
        "list": values,
        "tuple": tuple(values),
        "ndarray": np.array(values),
        "dict": {"close": values},
        "json": "[" + ",".join(repr(value) for value in values) + "]",
    }[kind]

    result = pyta.sma(data, period=period)

    assert type(result) is type(data)


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
