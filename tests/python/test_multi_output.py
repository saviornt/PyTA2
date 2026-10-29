"""The shared runners handle any number of outputs and parameters.

A fake native function (high, low, close in; two outputs out, with
parameters) drives `run_columns` and `run_columns_batch` directly, so these
tests pin the runners themselves, apart from any indicator's numbers. The
container matrices in `test_output.py` and `test_roundtrip.py` use the real
Stochastic (`pyta.stoch`) for the same shape.
"""

import json
from collections.abc import Callable, Sequence

import numpy as np
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv
from pyta._api import run_columns, run_columns_batch
from pyta._outputs import OutputNames
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, Slot

type Array = NDArray[np.float64]

SLOTS = (Slot("high", (HIGH,)), Slot("low", (LOW,)), Slot("close", (CLOSE, ADJ_CLOSE)))
NAMES = OutputNames("stoch", ("stoch_k", "stoch_d"), ("stoch",))


def fake(columns: Sequence[Array], k: int, d: int) -> list[Array]:
    """Not a Stochastic: two outputs from three columns, with warm-ups `k - 1` and `d - 1`."""
    high, low, close = columns
    if close.shape[0] < k:
        raise ValueError(f"not enough data: at least {k} values are required")
    first = high - low
    second = close * d
    first[: k - 1] = np.nan
    second[: d - 1] = np.nan
    return [first, second]


def fake_batch(
    datasets: Sequence[Sequence[Array]], k: int, d: int
) -> list[list[Array] | Exception]:
    results: list[list[Array] | Exception] = []
    for columns in datasets:
        try:
            results.append(fake(columns, k, d))
        except ValueError as error:
            results.append(error)
    return results


def frame_data(ohlcv: Ohlcv) -> dict[str, Array]:
    return {"High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close}


def test_dict_gets_one_key_per_output_with_parameters_passed_through(ohlcv: Ohlcv) -> None:
    result = run_columns(fake, NAMES, frame_data(ohlcv), (3, 2), None, SLOTS)

    assert list(result) == ["STOCH_K", "STOCH_D"]
    assert np.isnan(result["STOCH_K"][:2]).all()
    np.testing.assert_array_equal(result["STOCH_K"][2:], (ohlcv.high - ohlcv.low)[2:])
    np.testing.assert_array_equal(result["STOCH_D"][1:], ohlcv.close[1:] * 2)


def test_unnamed_input_gives_a_tuple_in_output_order(ohlcv: Ohlcv) -> None:
    array = np.column_stack([ohlcv.high, ohlcv.low, ohlcv.close])

    as_array = run_columns(fake, NAMES, array, (3, 2), None, SLOTS)
    as_tuple = run_columns(fake, NAMES, (ohlcv.high, ohlcv.low, ohlcv.close), (3, 2), None, SLOTS)

    assert isinstance(as_array, tuple)
    assert len(as_array) == 2
    assert all(isinstance(output, np.ndarray) for output in as_array)
    assert isinstance(as_tuple, tuple)
    assert all(isinstance(o, tuple) for o in as_tuple)
    np.testing.assert_array_equal(as_tuple[1], as_array[1])


def stack(ohlcv: Ohlcv) -> Array:
    return np.column_stack([ohlcv.high, ohlcv.low, ohlcv.close])


@pytest.mark.parametrize(
    ("make", "kind"),
    [
        (lambda o: stack(o).T, np.ndarray),  # (columns, rows)
        (lambda o: stack(o).tolist(), list),  # list of rows
        (lambda o: stack(o).T.tolist(), list),  # list of column lists
        (lambda o: [o.high, o.low, o.close], list),  # list of arrays
    ],
)
def test_more_unnamed_forms_give_a_tuple_in_output_order(
    ohlcv: Ohlcv, make: Callable[[Ohlcv], object], kind: type
) -> None:
    reference = run_columns(fake, NAMES, stack(ohlcv), (3, 2), None, SLOTS)

    result = run_columns(fake, NAMES, make(ohlcv), (3, 2), None, SLOTS)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert all(isinstance(output, kind) for output in result)
    for output, want in zip(result, reference, strict=True):
        np.testing.assert_array_equal(np.asarray(output), want)


@pytest.mark.parametrize("layout", ["rows", "columns"])
def test_json_array_of_arrays_gives_an_object_keyed_by_output(ohlcv: Ohlcv, layout: str) -> None:
    table = stack(ohlcv) if layout == "rows" else stack(ohlcv).T

    result = json.loads(run_columns(fake, NAMES, json.dumps(table.tolist()), (3, 2), None, SLOTS))

    assert list(result) == ["stoch_k", "stoch_d"]
    assert result["stoch_k"][:2] == [None, None]
    assert result["stoch_d"][1:] == (ohlcv.close[1:] * 2).tolist()


@pytest.mark.pandas
@pytest.mark.parametrize("named", [True, False])
def test_list_of_series_gives_a_tuple_of_series(ohlcv: Ohlcv, named: bool) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.DatetimeIndex(ohlcv.dates)
    names = ("Low", "Close", "High") if named else (None, None, None)
    values = (ohlcv.low, ohlcv.close, ohlcv.high) if named else (ohlcv.high, ohlcv.low, ohlcv.close)
    series = [pd.Series(v, index=index, name=n) for v, n in zip(values, names, strict=True)]

    result = run_columns(fake, NAMES, series, (3, 2), None, SLOTS)

    assert isinstance(result, tuple)
    assert [output.name for output in result] == (
        ["STOCH_K", "STOCH_D"] if named else ["stoch_k", "stoch_d"]
    )
    assert all(output.index.equals(index) for output in result)
    np.testing.assert_array_equal(result[1].to_numpy()[1:], ohlcv.close[1:] * 2)


@pytest.mark.pandas
def test_batch_with_the_new_forms_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    mismatched = [pd.Series(ohlcv.high), pd.Series(ohlcv.low, index=range(1, 301))]

    results = run_columns_batch(
        fake_batch, NAMES, [stack(ohlcv).T, mismatched, stack(ohlcv).tolist()], (3, 2), None, SLOTS
    )

    assert isinstance(results[0], tuple)
    assert isinstance(results[1], ValueError)
    assert "must share one index" in str(results[1])
    assert isinstance(results[2], tuple)
    assert all(isinstance(output, list) for output in results[2])


def test_json_records_and_object(ohlcv: Ohlcv) -> None:
    table = {"high": ohlcv.high.tolist(), "low": ohlcv.low.tolist(), "close": ohlcv.close.tolist()}
    records = [dict(zip(table, row, strict=True)) for row in zip(*table.values(), strict=True)]

    as_object = json.loads(run_columns(fake, NAMES, json.dumps(table), (3, 2), None, SLOTS))
    as_records = json.loads(run_columns(fake, NAMES, json.dumps(records), (3, 2), None, SLOTS))

    assert list(as_object) == ["stoch_k", "stoch_d"]
    assert as_object["stoch_k"][:2] == [None, None]
    assert as_records[0] == {"stoch_k": None, "stoch_d": None}
    assert [row["stoch_d"] for row in as_records] == as_object["stoch_d"]


@pytest.mark.pandas
def test_dataframe_keeps_its_index(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame(frame_data(ohlcv), index=pd.DatetimeIndex(ohlcv.dates))

    result = run_columns(fake, NAMES, frame, (3, 2), None, SLOTS)

    assert list(result.columns) == ["STOCH_K", "STOCH_D"]
    assert result.index.equals(frame.index)


def test_leading_nan_rows_shift_every_output(ohlcv: Ohlcv) -> None:
    data = {
        name: np.concatenate([np.full(5, np.nan), values])
        for name, values in frame_data(ohlcv).items()
    }

    result = run_columns(fake, NAMES, data, (3, 2), None, SLOTS)
    direct = run_columns(fake, NAMES, frame_data(ohlcv), (3, 2), None, SLOTS)

    for name in ("STOCH_K", "STOCH_D"):
        assert result[name].shape == (305,)
        assert np.isnan(result[name][:5]).all()
        np.testing.assert_array_equal(result[name][5:], direct[name])


def test_batch_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    short = {"high": ohlcv.high[:2], "low": ohlcv.low[:2], "close": ohlcv.close[:2]}

    results = run_columns_batch(
        fake_batch, NAMES, [frame_data(ohlcv), short, [1.0]], (3, 2), None, SLOTS
    )

    assert list(results[0]) == ["STOCH_K", "STOCH_D"]
    assert isinstance(results[1], ValueError)
    assert "at least 3 values" in str(results[1])
    assert isinstance(results[2], TypeError)
