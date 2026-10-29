"""The shared runners handle any number of outputs and parameters.

A fake native function stands in for a future multi-column, multi-output
indicator (Stochastic: high, low, close in; %K and %D out) to show it needs no
plumbing beyond declaring its slots, outputs and parameters.
"""

import json
from collections.abc import Sequence

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
