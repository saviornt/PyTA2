import json

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv


def series(n: int, seed: int) -> list[float]:
    """A synthetic random walk, for sizes the real fixture does not have."""
    rng = np.random.default_rng(seed)
    return (100.0 + np.cumsum(rng.uniform(-1.0, 1.0, n))).tolist()


def same(got, want):
    np.testing.assert_array_equal(got, want)


@pytest.mark.parametrize("name", ["sma", "rsi", "ema", "wma", "dema", "tema", "kama", "stddev"])
def test_list_matches_single_calls_in_order(name, ohlcv: Ohlcv):
    # Each real column, at a different length, so positions cannot be swapped silently.
    datasets = [
        ohlcv.open[:30].tolist(),
        ohlcv.high[:50].tolist(),
        ohlcv.close.tolist(),
        ohlcv.volume[-40:].tolist(),
    ]
    expected = [getattr(pyta, name)(d, period=5) for d in datasets]

    results = getattr(pyta.batch, name)(datasets, period=5)

    assert isinstance(results, list)
    assert len(results) == len(datasets)
    for got, want in zip(results, expected, strict=True):
        same(got, want)


def test_large_batch_matches_single_calls():
    datasets = [np.array(series(10_000, i)) for i in range(16)]

    results = pyta.batch.sma(datasets, period=20)

    for got, data in zip(results, datasets, strict=True):
        np.testing.assert_array_equal(got, pyta.sma(data, period=20))


def test_mapping_keeps_keys_and_order(ohlcv: Ohlcv):
    # One real dataset per quarter, keyed by quarter, in non-sorted order.
    quarters = {"2025Q3": slice(-126, -63), "2025Q1": slice(-252, -189), "2025Q4": slice(-63, None)}
    datasets = {key: ohlcv.close[part].tolist() for key, part in quarters.items()}

    results = pyta.batch.sma(datasets, period=5)

    assert isinstance(results, dict)
    assert list(results) == ["2025Q3", "2025Q1", "2025Q4"]
    for key, values in datasets.items():
        same(results[key], pyta.sma(values, period=5))


def test_mixed_containers_each_return_their_own_type(ohlcv: Ohlcv):
    values = ohlcv.close.tolist()
    datasets = [
        values,
        tuple(values),
        np.array(values),
        {"close": values},
        json.dumps(values),
    ]

    results = pyta.batch.sma(datasets, period=3)

    assert isinstance(results[0], list)
    assert isinstance(results[1], tuple)
    assert isinstance(results[2], np.ndarray)
    assert list(results[3]) == ["sma"]
    assert isinstance(results[4], str)

    expected = pyta.sma(np.array(values), period=3)
    for got in (results[0], results[1], results[2], results[3]["sma"]):
        same(np.asarray(got, dtype=np.float64), expected)
    from_json = [np.nan if v is None else v for v in json.loads(results[4])]
    same(np.array(from_json), expected)


@pytest.mark.pandas
def test_pandas_dataframe_and_series():
    pd = pytest.importorskip("pandas")
    values = series(20, 4)
    frame = pd.DataFrame({"Close": values}, index=pd.date_range("2026-01-01", periods=20))

    results = pyta.batch.sma([frame, frame["Close"]], period=3)

    assert list(results[0].columns) == ["SMA"]
    assert results[0].index.equals(frame.index)
    assert results[1].name == "SMA"


def test_column_applies_to_every_dataset():
    frames = [{"open": series(10, 1), "close": series(10, 2)} for _ in range(2)]

    results = pyta.batch.sma(frames, period=3, column="open")

    for result, frame in zip(results, frames, strict=True):
        same(result["sma"], pyta.sma(frame["open"], period=3))


def test_leading_nan_is_skipped_and_repadded():
    values = [float("nan"), float("nan"), *series(10, 5)]

    (result,) = pyta.batch.sma([values], period=3)

    same(result, pyta.sma(values, period=3))
    assert np.isnan(result[:4]).all()


def test_failures_are_returned_in_place_not_raised():
    good = series(20, 1)
    datasets = {
        "good": good,
        "short": [1.0, 2.0],  # period exceeds length (Rust)
        "gap": [1.0, float("nan"), 3.0, 4.0, 5.0],  # NaN after start (Python)
        "text": ["a", "b", "c"],  # not numbers (Python)
        "good2": good,
    }

    results = pyta.batch.sma(datasets, period=3)

    assert list(results) == list(datasets)
    same(results["good"], pyta.sma(good, period=3))
    same(results["good2"], results["good"])
    assert isinstance(results["short"], ValueError)
    assert isinstance(results["gap"], ValueError)
    assert isinstance(results["text"], TypeError)
    assert "exceeds" in str(results["short"])


def test_rsi_needs_period_plus_one():
    results = pyta.batch.rsi([series(5, 1), series(30, 1)], period=5)

    assert isinstance(results[0], ValueError)
    assert isinstance(results[1], list)


def test_all_datasets_failing_still_returns_a_result_for_each():
    results = pyta.batch.sma([[], [float("inf"), 1.0]], period=2)

    assert all(isinstance(r, ValueError) for r in results)


def test_empty_batch_returns_empty_container():
    assert pyta.batch.sma([], period=3) == []
    assert pyta.batch.sma({}, period=3) == {}


@pytest.mark.parametrize("datasets", ["[1, 2]", None, (series(5, 1),)])
def test_datasets_must_be_list_or_mapping(datasets):
    with pytest.raises(TypeError, match="list or a mapping"):
        pyta.batch.sma(datasets, period=3)


def test_list_of_non_datasets_fails_per_entry():
    results = pyta.batch.sma([1.0, series(10, 1)], period=3)

    assert isinstance(results[0], TypeError)
    assert isinstance(results[1], list)


@pytest.mark.parametrize("period", [0, -1, "3", 2.5, True])
def test_invalid_period_raises_for_the_whole_call(period):
    with pytest.raises((TypeError, ValueError)):
        pyta.batch.sma([series(10, 1)], period=period)


def test_invalid_column_type_raises():
    with pytest.raises(TypeError, match="column"):
        pyta.batch.sma([series(10, 1)], period=3, column=1)


def test_inputs_are_not_modified():
    data = np.array(series(20, 9))
    before = data.copy()

    pyta.batch.rsi([data], period=5)

    np.testing.assert_array_equal(data, before)
