"""Round-trip conformance: each container in gives the same container out (`output=None`).

One matrix runs every input form of `docs/API.md` §4 through each indicator
shape: SMA (one column, one output), MACD (one column, three outputs), CCI
(three columns, one output) and the fake multi-column, multi-output function of
`test_multi_output.py` (through `run_columns`). Each result is read back and
checked for its container type, length, output names and casing, pandas index
(values, name and order) and values, which must equal the plain NumPy-array
call exactly. A Hypothesis property repeats the value check on random data.

The `output=` conversions have their own matrix in `test_output.py`.
"""

import csv
import datetime as dt
import io
import json
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray
from ohlcv_data import Ohlcv
from test_output import SHAPES, Shape

type Array = NDArray[np.float64]

ROWS = 60
GAP = 2  # leading gaps in the cases that have them


# --- the data ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Data:
    """One dataset's columns as float64 arrays, and its dates as ISO strings."""

    open: Array
    high: Array
    low: Array
    close: Array
    volume: Array
    dates: list[str]

    @property
    def rows(self) -> int:
        return self.close.shape[0]

    @property
    def hlc(self) -> tuple[Array, Array, Array]:
        return self.high, self.low, self.close


def from_ohlcv(ohlcv: Ohlcv) -> Data:
    return Data(
        ohlcv.open[:ROWS].copy(),
        ohlcv.high[:ROWS].copy(),
        ohlcv.low[:ROWS].copy(),
        ohlcv.close[:ROWS].copy(),
        ohlcv.volume[:ROWS].copy(),
        ohlcv.dates[:ROWS],
    )


# --- the cases -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    """One input and how its default result reads back.

    `form` is the result's container: "list", "tuple", "numpy", "series",
    "frame", "dict" (each value in the `inner` form), "json_array", "records",
    "object" or "csv". `plain` holds the same values as float64 columns in slot
    order, for the NumPy call; `index` is the pandas index the result must keep.
    """

    data: object
    form: str
    casing: str
    plain: tuple[Array, ...]
    index: Any = None
    inner: str | None = None
    text: type | None = None


def _pd() -> Any:
    return pytest.importorskip("pandas")


def _gapped(values: Array) -> Array:
    out = values.copy()
    out[:GAP] = np.nan
    return out


def _ints(values: Array) -> NDArray[np.int64]:
    return (values * 100).astype(np.int64)


def _json_values(values: Array) -> list[float | None]:
    return [None if v != v else v for v in values.tolist()]


def _csv_text(columns: dict[str, list[str]]) -> str:
    rows = zip(*columns.values(), strict=True)
    return "\n".join([",".join(columns), *(",".join(row) for row in rows)]) + "\n"


def _fields(values: Array) -> list[str]:
    return ["" if v != v else repr(v) for v in values.tolist()]


def _records(columns: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(columns)
    return [dict(zip(keys, row, strict=True)) for row in zip(*columns.values(), strict=True)]


def _daily(data: Data, name: str | None = "Date") -> Any:
    return _pd().DatetimeIndex(data.dates, name=name)


def single_case(kind: str, data: Data) -> Case:
    close = data.close
    gapped = _gapped(close)
    one = (close,)

    match kind:
        # Unnamed one-series containers.
        case "list":
            return Case(close.tolist(), "list", "lower", one)
        case "list_gaps":
            return Case([None] * GAP + close[GAP:].tolist(), "list", "lower", (gapped,))
        case "list_strings":
            strings = ["", "NaN", *(f" {v!r} " for v in close[GAP:].tolist())]
            return Case(strings, "list", "lower", (gapped,))
        case "tuple":
            return Case(tuple(close.tolist()), "tuple", "lower", one)
        case "tuple_strings":
            return Case(tuple(map(repr, close.tolist())), "tuple", "lower", one)
        case "ndarray":
            return Case(close, "numpy", "lower", one)
        case "ndarray_int":
            ints = _ints(close)
            return Case(ints, "numpy", "lower", (ints.astype(np.float64),))
        case "ndarray_float32":
            small = close.astype(np.float32)
            return Case(small, "numpy", "lower", (small.astype(np.float64),))
        case "masked":
            mask = np.arange(data.rows) < GAP
            return Case(np.ma.masked_array(close, mask=mask), "numpy", "lower", (gapped,))
        # pandas Series, each index kind.
        case "series":
            pd = _pd()
            return Case(
                pd.Series(close, name="Close"), "series", "title", one, pd.RangeIndex(data.rows)
            )
        case "series_unnamed":
            pd = _pd()
            index = pd.Index(np.arange(data.rows) * 10, name="n")
            return Case(pd.Series(close, index=index), "series", "lower", one, index)
        case "series_dates":
            index = _daily(data)
            return Case(
                _pd().Series(close, index=index, name="close"), "series", "lower", one, index
            )
        case "series_datetime":
            pd = _pd()
            index = pd.date_range(
                "2024-01-02 09:30", periods=data.rows, freq="min", tz="America/New_York", name="ts"
            )
            return Case(pd.Series(close, index=index, name="CLOSE"), "series", "upper", one, index)
        case "series_python_dates":
            # Python dates, newest first: the order is kept, never sorted.
            pd = _pd()
            days = [dt.date(2024, 1, 1) + dt.timedelta(days=i) for i in range(data.rows)][::-1]
            index = pd.Index(days, dtype=object, name="day")
            return Case(pd.Series(close, index=index, name="close"), "series", "lower", one, index)
        case "series_non_unique":
            pd = _pd()
            index = pd.Index(np.arange(data.rows) // 2)
            return Case(pd.Series(close, index=index), "series", "lower", one, index)
        case "series_float64_na":
            pd = _pd()
            values = pd.array([pd.NA] * GAP + close[GAP:].tolist(), dtype="Float64")
            series = pd.Series(values, name="Close")
            return Case(series, "series", "title", (gapped,), pd.RangeIndex(data.rows))
        case "series_int64_na":
            pd = _pd()
            ints = _ints(close)
            values = pd.array([pd.NA] * GAP + ints[GAP:].tolist(), dtype="Int64")
            plain = _gapped(ints.astype(np.float64))
            return Case(
                pd.Series(values, name="close"),
                "series",
                "lower",
                (plain,),
                pd.RangeIndex(data.rows),
            )
        case "series_string":
            pd = _pd()
            values = [None] * GAP + [repr(v) for v in close[GAP:].tolist()]
            series = pd.Series(values, dtype="string", name="close")
            return Case(series, "series", "lower", (gapped,), pd.RangeIndex(data.rows))
        # DataFrames.
        case "frame":
            # yfinance's layout with extra non-numeric columns and an int volume.
            pd = _pd()
            frame = pd.DataFrame(
                {
                    "Date": data.dates,
                    "Open": data.open,
                    "High": data.high,
                    "Low": data.low,
                    "Close": close,
                    "Volume": data.volume.astype(np.int64),
                    "Symbol": "SPY",
                }
            )
            return Case(frame, "frame", "title", one, frame.index)
        case "frame_dates":
            index = _daily(data)
            frame = _pd().DataFrame({"OPEN": data.open, "CLOSE": close}, index=index)
            return Case(frame, "frame", "upper", one, index)
        case "frame_int":
            ints = _ints(close)
            frame = _pd().DataFrame({"close": ints, "volume": data.volume.astype(np.int64)})
            return Case(frame, "frame", "lower", (ints.astype(np.float64),), frame.index)
        case "frame_nullable":
            pd = _pd()
            values = pd.array([pd.NA] * GAP + close[GAP:].tolist(), dtype="Float64")
            volume = pd.array([pd.NA, *data.volume[1:].astype(np.int64).tolist()], dtype="Int64")
            index = pd.Index(np.arange(data.rows)[::-1], name="row")
            frame = pd.DataFrame({"Close": values, "Volume": volume}, index=index)
            return Case(frame, "frame", "title", (gapped,), index)
        case "frame_strings":
            # A frame built from AlphaVantage's JSON: numbered names, numbers as strings.
            pd = _pd()
            frame = pd.DataFrame(
                {
                    "1. open": list(map(repr, data.open.tolist())),
                    "4. close": list(map(repr, close.tolist())),
                },
                dtype=object,
            )
            return Case(frame, "frame", "lower", one, frame.index)
        # dicts.
        case "dict_list":
            return Case(
                {"open": data.open.tolist(), "close": close.tolist()},
                "dict",
                "lower",
                one,
                inner="list",
            )
        case "dict_tuple":
            return Case({"Close": tuple(close.tolist())}, "dict", "title", one, inner="tuple")
        case "dict_array":
            return Case(
                {"CLOSE": close, "VOLUME": data.volume}, "dict", "upper", one, inner="numpy"
            )
        case "dict_series":
            index = _daily(data)
            value = _pd().Series(close, index=index)
            return Case({"close": value}, "dict", "lower", one, index, inner="series")
        case "dict_mixed":
            # The column used sets the form: a tuple here, whatever the others are.
            pd = _pd()
            mixed = {
                "open": pd.Series(data.open),
                "high": data.high,
                "close": tuple(close.tolist()),
                "volume": data.volume.tolist(),
            }
            return Case(mixed, "dict", "lower", one, inner="tuple")
        case "dict_non_string_keys":
            extra = {"Close": close.tolist(), 7: ["x"] * data.rows, ("a", "b"): data.open}
            return Case(extra, "dict", "title", one, inner="list")
        case "dict_lone_non_string_key":
            return Case({0: close}, "dict", "lower", one, inner="numpy")
        case "dict_strings":
            strings = ["", *map(repr, close[1:].tolist())]
            plain = close.copy()
            plain[0] = np.nan
            return Case(
                {"date": data.dates, "close": strings}, "dict", "lower", (plain,), inner="list"
            )
        # JSON text.
        case "json_array":
            return Case(json.dumps(close.tolist()), "json_array", "lower", one, text=str)
        case "json_array_bytes":
            return Case(
                json.dumps(_json_values(gapped)).encode(),
                "json_array",
                "lower",
                (gapped,),
                text=bytes,
            )
        case "json_array_bytearray":
            return Case(
                bytearray(json.dumps(close.tolist()).encode()),
                "json_array",
                "lower",
                one,
                text=bytes,
            )
        case "json_array_strings":
            strings = [None, "", *map(repr, close[GAP:].tolist())]
            return Case(json.dumps(strings), "json_array", "lower", (gapped,), text=str)
        case "json_records":
            records = _records({"Date": data.dates, "Close": _json_values(gapped)})
            return Case(json.dumps(records), "records", "title", (gapped,), text=str)
        case "json_records_numbered":
            records = _records(
                {"timestamp": data.dates, "1. open": _fields(data.open), "4. close": _fields(close)}
            )
            return Case(
                bytearray(json.dumps(records).encode()), "records", "lower", one, text=bytes
            )
        case "json_object":
            obj = {"OPEN": data.open.tolist(), "CLOSE": close.tolist()}
            return Case(json.dumps(obj).encode(), "object", "upper", one, text=bytes)
        case "json_object_strings":
            obj = {"date": data.dates, "4. close": [None, *_fields(close[1:])]}
            plain = close.copy()
            plain[0] = np.nan
            return Case(json.dumps(obj), "object", "lower", (plain,), text=str)
        # CSV text.
        case "csv":
            text = _csv_text({"timestamp": data.dates, "close": _fields(gapped)})
            return Case(text, "csv", "lower", (gapped,), text=str)
        case "csv_bytes":
            text = _csv_text({"Date": data.dates, "Close": _fields(close)})
            return Case(text.encode(), "csv", "title", one, text=bytes)
        case "csv_bytearray":
            return Case(
                bytearray(_csv_text({"CLOSE": _fields(close)}).encode()),
                "csv",
                "upper",
                one,
                text=bytes,
            )
        case "csv_numbered":
            text = _csv_text(
                {"timestamp": data.dates, "1. open": _fields(data.open), "4. close": _fields(close)}
            )
            return Case(text.replace("\n", "\r\n"), "csv", "lower", one, text=str)
    raise AssertionError(kind)


def multi_case(kind: str, data: Data) -> Case:
    high, low, close = data.hlc
    hlc = data.hlc
    gapped = (_gapped(high), _gapped(low), close)

    match kind:
        # DataFrames.
        case "frame":
            pd = _pd()
            frame = pd.DataFrame(
                {
                    "Date": data.dates,
                    "Open": data.open,
                    "High": high,
                    "Low": low,
                    "Close": close,
                    "Adj Close": close * 0.99,
                    "Volume": data.volume.astype(np.int64),
                }
            )
            return Case(frame, "frame", "title", hlc, frame.index)
        case "frame_dates":
            index = _daily(data)
            frame = _pd().DataFrame({"HIGH": high, "LOW": low, "CLOSE": close}, index=index)
            return Case(frame, "frame", "upper", hlc, index)
        case "frame_int":
            ints = tuple(_ints(v) for v in hlc)
            frame = _pd().DataFrame({"high": ints[0], "low": ints[1], "close": ints[2]})
            return Case(
                frame, "frame", "lower", tuple(v.astype(np.float64) for v in ints), frame.index
            )
        case "frame_nullable":
            pd = _pd()
            frame = pd.DataFrame(
                {
                    "High": pd.array([pd.NA] * GAP + high[GAP:].tolist(), dtype="Float64"),
                    "Low": pd.array([pd.NA] * GAP + low[GAP:].tolist(), dtype="Float64"),
                    "Close": close,
                }
            )
            return Case(frame, "frame", "title", gapped, frame.index)
        case "frame_int64_na":
            pd = _pd()
            ints = tuple(_ints(v) for v in hlc)
            frame = pd.DataFrame(
                {
                    name: pd.array([pd.NA, *v[1:].tolist()], dtype="Int64")
                    for name, v in zip(("high", "low", "close"), ints, strict=True)
                }
            )
            plain = tuple(v.astype(np.float64) for v in ints)
            for v in plain:
                v[0] = np.nan
            return Case(frame, "frame", "lower", plain, frame.index)
        case "frame_strings":
            pd = _pd()
            frame = pd.DataFrame(
                {"2. high": _fields(high), "3. low": _fields(low), "4. close": _fields(close)},
                dtype="string",
            )
            return Case(frame, "frame", "lower", hlc, frame.index)
        case "frame_non_unique":
            pd = _pd()
            index = pd.Index(np.arange(data.rows) % 3, name="k")
            frame = pd.DataFrame({"Low": low, "Close": close, "High": high}, index=index)
            return Case(frame, "frame", "title", hlc, index)
        # dicts.
        case "dict_list":
            columns = {
                "open": data.open.tolist(),
                "high": high.tolist(),
                "low": low.tolist(),
                "close": close.tolist(),
            }
            return Case(columns, "dict", "lower", hlc, inner="list")
        case "dict_tuple":
            columns = {
                "High": tuple(high.tolist()),
                "Low": tuple(low.tolist()),
                "Close": tuple(close.tolist()),
            }
            return Case(columns, "dict", "title", hlc, inner="tuple")
        case "dict_array":
            return Case(
                {"HIGH": high, "LOW": low, "CLOSE": close}, "dict", "upper", hlc, inner="numpy"
            )
        case "dict_series":
            pd = _pd()
            index = _daily(data)
            columns = {
                name: pd.Series(v, index=index)
                for name, v in zip(("high", "low", "close"), hlc, strict=True)
            }
            return Case(columns, "dict", "lower", hlc, index, inner="series")
        case "dict_mixed_tuple_first":
            # The first input column (high) sets the form of every output.
            pd = _pd()
            columns = {"close": pd.Series(close), "low": low, "high": tuple(high.tolist())}
            return Case(columns, "dict", "lower", hlc, inner="tuple")
        case "dict_mixed_series_first":
            pd = _pd()
            index = pd.Index(np.arange(data.rows) + 100, name="i")
            columns = {
                "high": pd.Series(high, index=index),
                "low": low.tolist(),
                "close": tuple(close.tolist()),
            }
            return Case(columns, "dict", "lower", hlc, index, inner="series")
        case "dict_extra_keys":
            columns = {
                9: data.dates,
                "Volume": data.volume,
                "High": high,
                "Low": low,
                "Close": close.tolist(),
            }
            return Case(columns, "dict", "title", hlc, inner="numpy")
        case "dict_strings":
            columns = {"2. high": _fields(high), "3. low": _fields(low), "4. close": _fields(close)}
            return Case(columns, "dict", "lower", hlc, inner="list")
        # Lists and tuples of Series.
        case "series_list":
            pd = _pd()
            index = _daily(data)
            series = [
                pd.Series(v, index=index, name=n)
                for n, v in zip(("Close", "High", "Low"), (close, high, low), strict=True)
            ]
            return Case(series, "series", "title", hlc, index)
        case "series_tuple_unnamed":
            pd = _pd()
            index = pd.Index(np.arange(data.rows)[::-1])
            return Case(
                tuple(pd.Series(v, index=index) for v in hlc), "series", "lower", hlc, index
            )
        # Unnamed tables, in documented order.
        case "tuple_arrays":
            return Case(hlc, "tuple", "lower", hlc)
        case "tuple_lists":
            return Case(tuple(v.tolist() for v in gapped), "tuple", "lower", gapped)
        case "array_rows":
            return Case(np.column_stack(hlc), "numpy", "lower", hlc)
        case "array_columns":
            return Case(np.vstack(hlc), "numpy", "lower", hlc)
        case "array_int":
            ints = np.column_stack([_ints(v) for v in hlc])
            return Case(
                ints, "numpy", "lower", tuple(ints[:, i].astype(np.float64) for i in range(3))
            )
        case "list_rows":
            return Case(np.column_stack(hlc).tolist(), "list", "lower", hlc)
        case "list_columns":
            return Case([v.tolist() for v in hlc], "list", "lower", hlc)
        case "list_arrays":
            return Case(list(hlc), "list", "lower", hlc)
        # JSON text.
        case "json_object":
            obj = {
                "date": data.dates,
                "high": high.tolist(),
                "low": low.tolist(),
                "close": close.tolist(),
            }
            return Case(json.dumps(obj), "object", "lower", hlc, text=str)
        case "json_object_gaps":
            obj = {
                "High": _json_values(gapped[0]),
                "Low": _json_values(gapped[1]),
                "Close": close.tolist(),
            }
            return Case(json.dumps(obj).encode(), "object", "title", gapped, text=bytes)
        case "json_records":
            records = _records(
                {"HIGH": high.tolist(), "LOW": low.tolist(), "CLOSE": close.tolist()}
            )
            return Case(
                bytearray(json.dumps(records).encode()), "records", "upper", hlc, text=bytes
            )
        case "json_records_numbered":
            records = _records(
                {
                    "timestamp": data.dates,
                    "2. high": _fields(high),
                    "3. low": _fields(low),
                    "4. close": _fields(close),
                }
            )
            return Case(json.dumps(records), "records", "lower", hlc, text=str)
        case "json_rows":
            return Case(
                json.dumps(np.column_stack(hlc).tolist()), "json_array", "lower", hlc, text=str
            )
        case "json_columns":
            return Case(
                json.dumps([v.tolist() for v in hlc]).encode(),
                "json_array",
                "lower",
                hlc,
                text=bytes,
            )
        # CSV text.
        case "csv":
            text = _csv_text(
                {
                    "timestamp": data.dates,
                    "high": _fields(high),
                    "low": _fields(low),
                    "close": _fields(close),
                }
            )
            return Case(text, "csv", "lower", hlc, text=str)
        case "csv_gaps":
            text = _csv_text(
                {
                    "Date": data.dates,
                    "High": _fields(gapped[0]),
                    "Low": _fields(gapped[1]),
                    "Close": _fields(close),
                }
            )
            return Case(text.encode(), "csv", "title", gapped, text=bytes)
        case "csv_numbered":
            text = _csv_text(
                {"2. high": _fields(high), "3. low": _fields(low), "4. close": _fields(close)}
            )
            return Case(bytearray(text.encode()), "csv", "lower", hlc, text=bytes)
    raise AssertionError(kind)


PANDAS_SINGLE = {
    "series",
    "series_unnamed",
    "series_dates",
    "series_datetime",
    "series_python_dates",
    "series_non_unique",
    "series_float64_na",
    "series_int64_na",
    "series_string",
    "frame",
    "frame_dates",
    "frame_int",
    "frame_nullable",
    "frame_strings",
    "dict_series",
    "dict_mixed",
}
PLAIN_SINGLE = [
    "list",
    "list_gaps",
    "list_strings",
    "tuple",
    "tuple_strings",
    "ndarray",
    "ndarray_int",
    "ndarray_float32",
    "masked",
    "dict_list",
    "dict_tuple",
    "dict_array",
    "dict_non_string_keys",
    "dict_lone_non_string_key",
    "dict_strings",
    "json_array",
    "json_array_bytes",
    "json_array_bytearray",
    "json_array_strings",
    "json_records",
    "json_records_numbered",
    "json_object",
    "json_object_strings",
    "csv",
    "csv_bytes",
    "csv_bytearray",
    "csv_numbered",
]
PANDAS_MULTI = {
    "frame",
    "frame_dates",
    "frame_int",
    "frame_nullable",
    "frame_int64_na",
    "frame_strings",
    "frame_non_unique",
    "dict_series",
    "dict_mixed_tuple_first",
    "dict_mixed_series_first",
    "series_list",
    "series_tuple_unnamed",
}
PLAIN_MULTI = [
    "dict_list",
    "dict_tuple",
    "dict_array",
    "dict_extra_keys",
    "dict_strings",
    "tuple_arrays",
    "tuple_lists",
    "array_rows",
    "array_columns",
    "array_int",
    "list_rows",
    "list_columns",
    "list_arrays",
    "json_object",
    "json_object_gaps",
    "json_records",
    "json_records_numbered",
    "json_rows",
    "json_columns",
    "csv",
    "csv_gaps",
    "csv_numbered",
]


def _matrix() -> list[Any]:
    params: list[Any] = []
    for shape, pandas_kinds, plain_kinds in (
        ("sma", PANDAS_SINGLE, PLAIN_SINGLE),
        ("macd", PANDAS_SINGLE, PLAIN_SINGLE),
        ("cci", PANDAS_MULTI, PLAIN_MULTI),
        ("fake", PANDAS_MULTI, PLAIN_MULTI),
    ):
        params.extend(pytest.param(shape, kind, id=f"{shape}-{kind}") for kind in plain_kinds)
        params.extend(
            pytest.param(shape, kind, id=f"{shape}-{kind}", marks=pytest.mark.pandas)
            for kind in sorted(pandas_kinds)
        )
    return params


# --- reading a result back -----------------------------------------------------------------


@dataclass
class Read:
    """A default result read back: output names (None when unnamed), values, pandas index."""

    names: tuple[str, ...] | None
    values: list[Array]
    index: Any = None
    dtypes: list[Any] = field(default_factory=list)


_UNNAMED = {"list": list, "tuple": tuple, "numpy": np.ndarray}


def _outputs(result: object, count: int) -> list[Any]:
    """One output alone, several as a tuple of them."""
    if count == 1:
        return [result]
    assert type(result) is tuple
    assert len(result) == count
    return list(result)


def _from_text(result: object, case: Case) -> str:
    assert type(result) is case.text
    return result.decode() if isinstance(result, bytes) else result  # type: ignore[return-value]


def read(result: object, case: Case, count: int) -> Read:
    """Checks that `result` has the container of `case.form` and reads it back."""
    match case.form:
        case "list" | "tuple" | "numpy":
            outputs = _outputs(result, count)
            assert all(type(output) is _UNNAMED[case.form] for output in outputs)
            dtypes = [output.dtype for output in outputs] if case.form == "numpy" else []
            return Read(None, [np.asarray(o, dtype=np.float64) for o in outputs], dtypes=dtypes)
        case "series":
            pd = sys.modules["pandas"]
            outputs = _outputs(result, count)
            assert all(type(output) is pd.Series for output in outputs)
            for output in outputs[1:]:
                assert output.index is outputs[0].index or output.index.equals(outputs[0].index)
            return Read(
                tuple(o.name for o in outputs),
                [o.to_numpy() for o in outputs],
                outputs[0].index,
                [o.dtype for o in outputs],
            )
        case "frame":
            pd = sys.modules["pandas"]
            assert type(result) is pd.DataFrame
            frame: Any = result
            names = tuple(frame.columns)
            return Read(
                names, [frame[n].to_numpy() for n in names], frame.index, list(frame.dtypes)
            )
        case "dict":
            assert type(result) is dict
            mapping: dict[str, Any] = result  # type: ignore[assignment]
            values = list(mapping.values())
            if case.inner == "series":
                pd = sys.modules["pandas"]
                assert all(type(v) is pd.Series for v in values)
                index = values[0].index
                assert all(v.index.equals(index) for v in values)
                return Read(tuple(mapping), [v.to_numpy() for v in values], index)
            assert case.inner is not None
            assert all(type(v) is _UNNAMED[case.inner] for v in values)
            return Read(tuple(mapping), [np.asarray(v, dtype=np.float64) for v in values])
        case "json_array" | "records" | "object":
            parsed = json.loads(_from_text(result, case))
            if case.form == "json_array" and count == 1:
                assert type(parsed) is list
                return Read(None, [_floats(parsed)])
            if case.form == "records":
                assert type(parsed) is list
                names = tuple(parsed[0])
                assert all(tuple(row) == names for row in parsed)
                return Read(names, [_floats([row[n] for row in parsed]) for n in names])
            assert type(parsed) is dict
            return Read(tuple(parsed), [_floats(v) for v in parsed.values()])
        case "csv":
            text = _from_text(result, case)
            assert text.endswith("\n")
            assert "\r" not in text
            header, *rows = list(csv.reader(io.StringIO(text)))
            if len(header) == 1:  # a one-column CSV writes an empty field as a blank line
                rows = [row or [""] for row in rows]
            columns = list(zip(*rows, strict=True))
            return Read(
                tuple(header), [np.array([float(f) if f else np.nan for f in c]) for c in columns]
            )
    raise AssertionError(case.form)


def _floats(items: list[Any]) -> Array:
    return np.array([np.nan if item is None else item for item in items], dtype=np.float64)


def expected(shape: Shape, case: Case) -> list[Array]:
    """The default call on the plain NumPy array(s), as a list of outputs."""
    data = case.plain[0] if shape.columns == 1 else np.column_stack(case.plain)
    reference = shape.call(data, None)
    return [reference] if isinstance(reference, np.ndarray) else list(reference)


def check(shape: Shape, case: Case) -> None:
    """Runs `case` through `shape` and checks the result against the NumPy call."""
    names = shape.names[case.casing]
    want = expected(shape, case)

    got = read(shape.call(case.data, None), case, len(names))

    # Length and values: exactly the NumPy call's, NaN in the same places.
    assert len(got.values) == len(names)
    for values, reference in zip(got.values, want, strict=True):
        assert values.shape == (case.plain[0].shape[0],)
        np.testing.assert_array_equal(values, reference)
    assert all(dtype == np.float64 for dtype in got.dtypes)

    # Names and casing: unnamed forms have none, except several outputs from a JSON array.
    if case.form in _UNNAMED or (case.form == "json_array" and len(names) == 1):
        assert got.names is None
    else:
        assert got.names == names

    # The pandas index: the same values, name and order.
    if case.index is not None:
        assert got.index.equals(case.index)
        assert got.index.name == case.index.name
        assert got.index.dtype == case.index.dtype
    else:
        assert got.index is None or case.form == "frame"


# --- the matrix ----------------------------------------------------------------------------


@pytest.mark.parametrize(("shape_name", "kind"), _matrix())
def test_every_container_round_trips_for_every_shape(
    ohlcv: Ohlcv, shape_name: str, kind: str
) -> None:
    shape = SHAPES[shape_name]
    data = from_ohlcv(ohlcv)
    case = single_case(kind, data) if shape.columns == 1 else multi_case(kind, data)

    check(shape, case)


# --- Hypothesis: random valid data, every container ----------------------------------------

PRICE = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
SPREAD = st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False)


@st.composite
def datasets(draw: st.DrawFn) -> Data:
    """Random OHLCV with high >= close >= low, long enough for every shape after the gaps."""
    rows = draw(st.integers(min_value=16, max_value=80))
    close = np.array(draw(st.lists(PRICE, min_size=rows, max_size=rows)))
    up = np.array(draw(st.lists(SPREAD, min_size=rows, max_size=rows)))
    down = np.array(draw(st.lists(SPREAD, min_size=rows, max_size=rows)))
    start = dt.date(2024, 1, 1)
    dates = [(start + dt.timedelta(days=i)).isoformat() for i in range(rows)]
    volume = np.floor(np.abs(close)) * 10
    return Data(close.copy(), close + up, close - down, close, volume, dates)


def _shape_and_kind(pandas: bool) -> st.SearchStrategy[tuple[str, str]]:
    single = sorted(PANDAS_SINGLE) if pandas else PLAIN_SINGLE
    multi = sorted(PANDAS_MULTI) if pandas else PLAIN_MULTI
    return st.one_of(
        st.tuples(st.sampled_from(["sma", "macd"]), st.sampled_from(single)),
        st.tuples(st.sampled_from(["cci", "fake"]), st.sampled_from(multi)),
    )


def _random_case(shape: Shape, kind: str, data: Data) -> Case:
    return single_case(kind, data) if shape.columns == 1 else multi_case(kind, data)


@settings(max_examples=60, deadline=None)
@given(datasets(), _shape_and_kind(pandas=False))
def test_random_data_gives_the_numpy_values_in_every_container(
    data: Data, shape_and_kind: tuple[str, str]
) -> None:
    shape_name, kind = shape_and_kind
    shape = SHAPES[shape_name]

    check(shape, _random_case(shape, kind, data))


@pytest.mark.pandas
@settings(max_examples=40, deadline=None)
@given(datasets(), _shape_and_kind(pandas=True))
def test_random_data_gives_the_numpy_values_in_every_pandas_container(
    data: Data, shape_and_kind: tuple[str, str]
) -> None:
    shape_name, kind = shape_and_kind
    shape = SHAPES[shape_name]

    check(shape, _random_case(shape, kind, data))
