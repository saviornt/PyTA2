"""`output=`: every input container converts to every target, for every indicator shape.

The matrix runs each input container through each target for SMA (one column,
one output), MACD (one column, three outputs), CCI (three columns, one output)
and the fake multi-column, multi-output function of `test_multi_output.py`
(through `run_columns`). Each result is decoded back to names, values and index
and compared with the default call on the same data, exactly.
"""

import csv
import datetime as dt
import io
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pyta
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray
from ohlcv_data import Ohlcv
from pyta._api import run_columns, run_columns_batch
from test_multi_output import NAMES as FAKE_NAMES
from test_multi_output import SLOTS as FAKE_SLOTS
from test_multi_output import fake, fake_batch

type Array = NDArray[np.float64]

TARGETS = ["list", "tuple", "numpy", "pandas", "dict", "json", "json_bytes", "csv", "csv_bytes"]
NAMED = {"pandas", "dict", "json", "json_bytes", "csv", "csv_bytes"}
ROWS = 60


# --- the indicator shapes -------------------------------------------------------------------


@dataclass(frozen=True)
class Shape:
    """One indicator shape: how to call it, and its output names in each casing."""

    call: Callable[[object, object], Any]
    batch: Callable[[object, object], Any]
    names: dict[str, tuple[str, ...]]
    columns: int


SHAPES = {
    "sma": Shape(
        lambda data, output: pyta.sma(data, 5, output=output),  # type: ignore[call-overload]
        lambda data, output: pyta.batch.sma(data, 5, output=output),
        {"lower": ("sma",), "upper": ("SMA",), "title": ("SMA",)},
        1,
    ),
    "macd": Shape(
        lambda data, output: pyta.macd(data, 3, 8, 4, output=output),
        lambda data, output: pyta.batch.macd(data, 3, 8, 4, output=output),
        {
            "lower": ("macd", "macd_signal", "macd_hist"),
            "upper": ("MACD", "MACD_SIGNAL", "MACD_HIST"),
            "title": ("MACD", "MACD_Signal", "MACD_Hist"),
        },
        1,
    ),
    "cci": Shape(
        lambda data, output: pyta.cci(data, 5, output=output),  # type: ignore[call-overload]
        lambda data, output: pyta.batch.cci(data, 5, output=output),
        {"lower": ("cci",), "upper": ("CCI",), "title": ("CCI",)},
        3,
    ),
    "fake": Shape(
        lambda data, output: run_columns(
            fake, FAKE_NAMES, data, (3, 2), None, FAKE_SLOTS, None, output
        ),
        lambda data, output: run_columns_batch(
            fake_batch, FAKE_NAMES, data, (3, 2), None, FAKE_SLOTS, None, output
        ),
        {
            "lower": ("stoch_k", "stoch_d"),
            "upper": ("STOCH_K", "STOCH_D"),
            "title": ("STOCH_K", "STOCH_D"),
        },
        3,
    ),
}


# --- the input containers -------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    """One input: the data, the casing of its names, and its pandas index (or None)."""

    data: object
    casing: str
    index: Any = None


def _frame(columns: dict[str, Array], index: Any = None) -> Any:
    pd = pytest.importorskip("pandas")
    return pd.DataFrame(columns, index=index)


def _dates(ohlcv: Ohlcv) -> Any:
    pd = pytest.importorskip("pandas")
    return pd.DatetimeIndex(ohlcv.dates[:ROWS], name="Date")


def _csv(columns: dict[str, Array]) -> str:
    rows = zip(*(values.tolist() for values in columns.values()), strict=True)
    return "\n".join([",".join(columns), *(",".join(map(repr, row)) for row in rows)]) + "\n"


def single_case(kind: str, ohlcv: Ohlcv) -> Case:
    close = ohlcv.close[:ROWS].copy()
    pd: Any = None
    if kind.startswith(("series", "frame", "dict_series")):
        pd = pytest.importorskip("pandas")

    match kind:
        case "list":
            return Case(close.tolist(), "lower")
        case "tuple":
            return Case(tuple(close.tolist()), "lower")
        case "ndarray":
            return Case(close, "lower")
        case "series":
            return Case(pd.Series(close, name="Close"), "title", pd.RangeIndex(ROWS))
        case "series_dates":
            dates = _dates(ohlcv)
            return Case(pd.Series(close, index=dates, name="close"), "lower", dates)
        case "frame":
            frame = _frame({"Open": ohlcv.open[:ROWS], "Close": close})
            return Case(frame, "title", frame.index)
        case "frame_dates":
            dates = _dates(ohlcv)
            return Case(_frame({"CLOSE": close}, dates), "upper", dates)
        case "dict":
            return Case({"open": ohlcv.open[:ROWS], "close": close.tolist()}, "lower")
        case "dict_series":
            dates = _dates(ohlcv)
            return Case({"Close": pd.Series(close, index=dates)}, "title", dates)
        case "json":
            return Case(json.dumps({"close": close.tolist()}), "lower")
        case "json_bytes":
            records = [{"Close": value} for value in close.tolist()]
            return Case(json.dumps(records).encode(), "title")
        case "csv":
            return Case(_csv({"timestamp": np.arange(ROWS) * 1.0, "close": close}), "lower")
        case "csv_bytes":
            return Case(_csv({"CLOSE": close}).encode(), "upper")
    raise AssertionError(kind)


def multi_case(kind: str, ohlcv: Ohlcv) -> Case:
    high, low, close = ohlcv.high[:ROWS], ohlcv.low[:ROWS], ohlcv.close[:ROWS]
    lower = {"high": high, "low": low, "close": close}
    title = {"High": high, "Low": low, "Close": close}
    pd: Any = None
    if kind.startswith(("series", "frame", "dict_series")):
        pd = pytest.importorskip("pandas")

    match kind:
        case "frame":
            frame = _frame(title)
            return Case(frame, "title", frame.index)
        case "frame_dates":
            dates = _dates(ohlcv)
            return Case(_frame({k.upper(): v for k, v in lower.items()}, dates), "upper", dates)
        case "dict":
            return Case(dict(lower), "lower")
        case "dict_series":
            dates = _dates(ohlcv)
            return Case({k: pd.Series(v, index=dates) for k, v in title.items()}, "title", dates)
        case "series_list":
            dates = _dates(ohlcv)
            return Case(
                [pd.Series(v, index=dates, name=k) for k, v in lower.items()], "lower", dates
            )
        case "json":
            return Case(json.dumps({k: v.tolist() for k, v in lower.items()}), "lower")
        case "json_bytes":
            rows = zip(high.tolist(), low.tolist(), close.tolist(), strict=True)
            records = [{"High": h, "Low": lo, "Close": c} for h, lo, c in rows]
            return Case(json.dumps(records).encode(), "title")
        case "csv":
            return Case(_csv(lower), "lower")
        case "csv_bytes":
            return Case(_csv({k.upper(): v for k, v in lower.items()}).encode(), "upper")
        case "array_2d":
            return Case(np.column_stack([high, low, close]), "lower")
        case "tuple":
            return Case((high, low, close), "lower")
        case "list_of_lists":
            return Case([high.tolist(), low.tolist(), close.tolist()], "lower")
    raise AssertionError(kind)


PANDAS_KINDS = {"series", "series_dates", "frame", "frame_dates", "dict_series", "series_list"}
SINGLE_KINDS = [
    "list",
    "tuple",
    "ndarray",
    "series",
    "series_dates",
    "frame",
    "frame_dates",
    "dict",
    "dict_series",
    "json",
    "json_bytes",
    "csv",
    "csv_bytes",
]
MULTI_KINDS = [
    "frame",
    "frame_dates",
    "dict",
    "dict_series",
    "series_list",
    "json",
    "json_bytes",
    "csv",
    "csv_bytes",
    "array_2d",
    "tuple",
    "list_of_lists",
]


def _matrix() -> list[Any]:
    params: list[Any] = []
    for shape, kinds in (
        ("sma", SINGLE_KINDS),
        ("macd", SINGLE_KINDS),
        ("cci", MULTI_KINDS),
        ("fake", MULTI_KINDS),
    ):
        for kind in kinds:
            for target in TARGETS:
                needs_pandas = kind in PANDAS_KINDS or target == "pandas"
                marks = [pytest.mark.pandas] if needs_pandas else []
                params.append(pytest.param(shape, kind, target, marks=marks))
    return params


# --- decoding a result ----------------------------------------------------------------------


@dataclass
class Decoded:
    """A result read back: output names, values, and the index field (or None)."""

    names: tuple[str, ...] | None
    values: list[Array]
    index_name: str | None = None
    index: list[Any] | None = None


def _floats(items: Sequence[object]) -> Array:
    return np.array([np.nan if item is None else item for item in items], dtype=np.float64)


def _csv_float(field: str) -> float:
    return float(field) if field else np.nan


def decode(result: object, target: str, count: int, indexed: bool) -> Decoded:
    """Checks the target's type and shape and reads `result` back."""
    match target:
        case "numpy" | "list" | "tuple":
            kind = {"numpy": np.ndarray, "list": list, "tuple": tuple}[target]
            outputs = [result] if count == 1 else list(result)  # type: ignore[call-overload]
            if count > 1:
                assert isinstance(result, tuple)
                assert len(outputs) == count
            assert all(type(output) is kind for output in outputs)
            return Decoded(None, [np.asarray(output, dtype=np.float64) for output in outputs])
        case "pandas":
            pd = sys.modules["pandas"]
            if count == 1:
                assert type(result) is pd.Series
                return Decoded((result.name,), [result.to_numpy()], index=result.index)  # type: ignore[attr-defined]
            assert type(result) is pd.DataFrame
            frame: Any = result
            return Decoded(
                tuple(frame.columns),
                [frame[name].to_numpy() for name in frame.columns],
                index=frame.index,
            )
        case "dict":
            assert type(result) is dict
            mapping: dict[str, Any] = result  # type: ignore[assignment]
            keys = list(mapping)
            assert all(type(value) is np.ndarray for value in mapping.values())
            if indexed:
                return Decoded(
                    tuple(keys[1:]),
                    [mapping[k] for k in keys[1:]],
                    keys[0],
                    mapping[keys[0]].tolist(),
                )
            return Decoded(tuple(keys), [mapping[k] for k in keys])
        case "json" | "json_bytes":
            assert type(result) is (str if target == "json" else bytes)
            obj: dict[str, list[Any]] = json.loads(result)  # type: ignore[arg-type]
            assert type(obj) is dict
            keys = list(obj)
            start = 1 if indexed else 0
            return Decoded(
                tuple(keys[start:]),
                [_floats(obj[k]) for k in keys[start:]],
                keys[0] if indexed else None,
                obj[keys[0]] if indexed else None,
            )
        case "csv" | "csv_bytes":
            assert type(result) is (str if target == "csv" else bytes)
            text = result if isinstance(result, str) else result.decode()  # type: ignore[union-attr]
            assert text.endswith("\n")
            assert "\r" not in text
            header, *rows = list(csv.reader(io.StringIO(text)))
            if len(header) == 1:  # a one-column CSV writes an empty field as a blank line
                rows = [row or [""] for row in rows]
            columns = list(zip(*rows, strict=True))
            start = 1 if indexed else 0
            return Decoded(
                tuple(header[start:]),
                [np.array([_csv_float(f) for f in column]) for column in columns[start:]],
                header[0] if indexed else None,
                list(columns[0]) if indexed else None,
            )
    raise AssertionError(target)


def _iso(index: Any) -> list[Any]:
    """The index as JSON writes it: ISO dates for a daily DatetimeIndex, else plain values."""
    if index.dtype.kind == "M":
        return [value.date().isoformat() for value in index]
    return index.tolist()


def _expected(shape: Shape, case: Case, ohlcv: Ohlcv) -> list[Array]:
    """The default call on plain NumPy input, as a list of outputs."""
    if shape.columns == 1:
        reference = shape.call(ohlcv.close[:ROWS].copy(), None)
    else:
        reference = shape.call(
            np.column_stack([ohlcv.high[:ROWS], ohlcv.low[:ROWS], ohlcv.close[:ROWS]]), None
        )
    return [reference] if isinstance(reference, np.ndarray) else list(reference)


@pytest.mark.parametrize(("shape_name", "kind", "target"), _matrix())
def test_every_container_converts_to_every_target(
    ohlcv: Ohlcv, shape_name: str, kind: str, target: str
) -> None:
    shape = SHAPES[shape_name]
    case = single_case(kind, ohlcv) if shape.columns == 1 else multi_case(kind, ohlcv)
    names = shape.names[case.casing]
    expected = _expected(shape, case, ohlcv)
    indexed = case.index is not None and target in NAMED and target != "pandas"

    decoded = decode(shape.call(case.data, target), target, len(names), indexed)

    # Values equal the default call exactly, NaN in the same places.
    assert len(decoded.values) == len(names)
    for got, want in zip(decoded.values, expected, strict=True):
        np.testing.assert_array_equal(got, want)

    # Names and casing, as in the default output.
    if target in NAMED:
        assert decoded.names == names

    # The index: carried to named targets, dropped for unnamed ones.
    if target == "pandas":
        pd = sys.modules["pandas"]
        want_index = pd.RangeIndex(ROWS) if case.index is None else case.index
        assert decoded.index.equals(want_index)
        assert decoded.index.name == want_index.name
    elif indexed:
        assert decoded.index_name == (case.index.name or "index")
        if target == "dict":
            np.testing.assert_array_equal(np.asarray(decoded.index), case.index.to_numpy())
        elif target.startswith("json"):
            assert decoded.index == _iso(case.index)
        else:
            assert decoded.index == [str(value) for value in _iso(case.index)]


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("shape_name", list(SHAPES))
def test_batch_shares_output_and_keeps_failures_in_place(
    ohlcv: Ohlcv, shape_name: str, target: str
) -> None:
    if target == "pandas":
        pytest.importorskip("pandas")
    shape = SHAPES[shape_name]
    case = single_case("dict", ohlcv) if shape.columns == 1 else multi_case("dict", ohlcv)
    names = shape.names[case.casing]
    bad = {"close": [1.0, 2.0]} if shape.columns == 1 else {"high": [1.0], "low": [2.0]}

    listed = shape.batch([case.data, bad, case.data], target)
    mapped = shape.batch({"a": case.data, "b": bad}, target)

    assert isinstance(listed[1], ValueError)
    assert isinstance(mapped["b"], ValueError)
    single = shape.call(case.data, target)
    for result in (listed[0], listed[2], mapped["a"]):
        got = decode(result, target, len(names), indexed=False)
        want = decode(single, target, len(names), indexed=False)
        assert got.names == want.names
        for a, b in zip(got.values, want.values, strict=True):
            np.testing.assert_array_equal(a, b)


# --- JSON and CSV conventions ---------------------------------------------------------------


def test_json_writes_null_and_csv_an_empty_field_for_nan() -> None:
    data = [1.0, 2.0, 3.0]

    assert pyta.sma(data, 2, output="json") == '{"sma":[null,1.5,2.5]}'
    assert pyta.sma(data, 2, output="json_bytes") == b'{"sma":[null,1.5,2.5]}'
    assert pyta.sma(data, 2, output="csv") == "sma\n\n1.5\n2.5\n"
    assert pyta.sma(data, 2, output="csv_bytes") == b"sma\n\n1.5\n2.5\n"
    assert pyta.macd(list(range(1, 12)), 2, 3, 2, output="csv").startswith(
        "macd,macd_signal,macd_hist\n,,\n"
    )


def test_csv_numbers_are_shortest_round_trip_repr() -> None:
    data = [0.1, 0.2, 1e200]

    text = pyta.sma(data, 1, output="csv")

    assert text == "sma\n0.1\n0.2\n1e+200\n"


@pytest.mark.pandas
def test_dates_become_iso_8601_strings() -> None:
    pd = pytest.importorskip("pandas")
    daily = pd.date_range("2024-01-02", periods=3)
    intraday = pd.DatetimeIndex(["2024-01-02 09:30", "2024-01-02 09:31", None])
    aware = pd.date_range("2024-01-02", periods=3, tz="America/New_York")

    def index(output: str, idx: Any) -> Any:
        result = pyta.sma(pd.Series([1.0, 2.0, 3.0], index=idx), 1, output=output)
        return json.loads(result)["index"] if output == "json" else result.splitlines()

    assert index("json", daily) == ["2024-01-02", "2024-01-03", "2024-01-04"]
    assert index("json", intraday) == ["2024-01-02T09:30:00", "2024-01-02T09:31:00", None]
    assert index("json", aware)[0] == "2024-01-02T00:00:00-05:00"
    assert index("csv", intraday) == [
        "index,sma",
        "2024-01-02T09:30:00,1.0",
        "2024-01-02T09:31:00,2.0",
        ",3.0",
    ]


@pytest.mark.pandas
def test_python_date_and_number_index_values() -> None:
    pd = pytest.importorskip("pandas")
    values = [1.0, 2.0, 3.0]

    def first(idx: list[Any], output: str = "json") -> Any:
        series = pd.Series(values, index=pd.Index(idx, dtype=object, name="when"))
        result = pyta.sma(series, 1, output=output)
        return json.loads(result)["when"] if output == "json" else result

    assert first([dt.date(2024, 1, 2), dt.date(2024, 1, 3), None]) == [
        "2024-01-02",
        "2024-01-03",
        None,
    ]
    assert first([dt.datetime(2024, 1, 2, 9, 30), dt.datetime(2024, 1, 3), "x"]) == [
        "2024-01-02T09:30:00",
        "2024-01-03T00:00:00",
        "x",
    ]
    assert first([1, 2.5, float("nan")]) == [1, 2.5, None]
    assert first([1, 2.5, float("nan")], "csv") == "when,sma\n1,1.0\n2.5,2.0\n,3.0\n"
    assert first([np.int64(7), True, "a,b"], "csv") == 'when,sma\n7,1.0\nTrue,2.0\n"a,b",3.0\n'


@pytest.mark.pandas
@pytest.mark.parametrize("output", ["json", "json_bytes", "csv", "csv_bytes"])
def test_an_index_json_cannot_hold_is_a_type_error(output: str) -> None:
    pd = pytest.importorskip("pandas")
    periods = pd.Series([1.0, 2.0], index=pd.period_range("2024-01", periods=2, freq="M"))
    infinite = pd.Series([1.0, 2.0], index=pd.Index([1.0, float("inf")]))

    with pytest.raises(TypeError, match=r"index 'index' value .* at position 0 \(Period\)"):
        pyta.sma(periods, 1, output=output)
    with pytest.raises(TypeError, match="replace infinite index values"):
        pyta.sma(infinite, 1, output=output)

    # The pandas and dict targets keep any index.
    assert pyta.sma(periods, 1, output="pandas").index.equals(periods.index)
    assert list(pyta.sma(periods, 1, output="dict")) == ["index", "sma"]


@pytest.mark.pandas
def test_a_conversion_error_stays_in_place_in_a_batch() -> None:
    pd = pytest.importorskip("pandas")
    periods = pd.Series([1.0, 2.0], index=pd.period_range("2024-01", periods=2, freq="M"))
    frame = pd.DataFrame(
        {"high": [2.0, 3.0], "low": [1.0, 2.0], "close": [1.5, 2.5]},
        index=pd.period_range("2024-01", periods=2, freq="M"),
    )

    results = pyta.batch.sma([[1.0, 2.0], periods], 1, output="json")
    columns = pyta.batch.cci({"ok": frame.reset_index(drop=True), "bad": frame}, 1, output="csv")

    assert results[0] == '{"sma":[1.0,2.0]}'
    assert isinstance(results[1], TypeError)
    assert columns["ok"] == "index,cci\n0,0.0\n1,0.0\n"
    assert isinstance(columns["bad"], TypeError)


@pytest.mark.pandas
def test_multiindex_gives_one_field_per_level() -> None:
    pd = pytest.importorskip("pandas")
    index = pd.MultiIndex.from_tuples(
        [("SPY", "2024-01-02"), ("SPY", "2024-01-03")], names=["symbol", None]
    )
    series = pd.Series([1.0, 2.0], index=index)

    as_json = json.loads(pyta.sma(series, 1, output="json"))
    as_dict = pyta.sma(series, 1, output="dict")

    assert as_json == {
        "symbol": ["SPY", "SPY"],
        "level_1": ["2024-01-02", "2024-01-03"],
        "sma": [1.0, 2.0],
    }
    assert pyta.sma(series, 1, output="csv") == (
        "symbol,level_1,sma\nSPY,2024-01-02,1.0\nSPY,2024-01-03,2.0\n"
    )
    assert list(as_dict) == ["symbol", "level_1", "sma"]
    assert pyta.sma(series, 1, output="pandas").index.equals(index)


@pytest.mark.pandas
def test_an_index_named_like_an_output_raises() -> None:
    pd = pytest.importorskip("pandas")
    series = pd.Series([1.0, 2.0], index=pd.Index([0, 1], name="sma"))
    doubled = pd.Series(
        [1.0, 2.0], index=pd.MultiIndex.from_tuples([(0, 0), (0, 1)], names=["a", "a"])
    )

    with pytest.raises(ValueError, match="index is named 'sma', which is also an output"):
        pyta.sma(series, 1, output="dict")
    with pytest.raises(ValueError, match="index is named 'a'"):
        pyta.sma(doubled, 1, output="json")


# --- fixed shapes ---------------------------------------------------------------------------


def test_the_inputs_own_container_still_gets_the_targets_fixed_shape() -> None:
    as_dict = pyta.sma({"close": [1.0, 2.0, 3.0]}, 2, output="dict")
    records = pyta.sma('[{"close": 1}, {"close": 2}]', 1, output="json")
    array = pyta.sma("[1, 2, 3]", 2, output="json")

    assert type(as_dict["sma"]) is np.ndarray
    assert records == '{"sma":[1.0,2.0]}'
    assert array == '{"sma":[null,1.5,2.5]}'


@pytest.mark.pandas
def test_a_dataframe_to_pandas_is_a_series_for_one_output() -> None:
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=[10, 20, 30])

    result = pyta.sma(frame, 2, output="pandas")
    several = pyta.macd(pd.Series(np.arange(1.0, 12.0)), 2, 3, 2, output="pandas")

    assert type(result) is pd.Series
    assert result.name == "sma"
    assert list(result.index) == [10, 20, 30]
    assert type(several) is pd.DataFrame
    assert list(several.columns) == ["macd", "macd_signal", "macd_hist"]


def test_output_none_is_the_default() -> None:
    data = {"close": [1.0, 2.0, 3.0]}

    assert pyta.sma(data, 1, output=None) == pyta.sma(data, 1) == {"sma": [1.0, 2.0, 3.0]}
    assert pyta.batch.sma([data], 1, output=None) == pyta.batch.sma([data], 1)


# --- invalid targets and missing pandas -----------------------------------------------------


@pytest.mark.parametrize("output", ["xml", "JSON", "", 5, ["json"]])
def test_an_invalid_target_raises_before_any_work(output: object) -> None:
    message = "output must be None or one of 'list', 'tuple', 'numpy', 'pandas', 'dict'"

    # Invalid JSON would raise its own error if the input were read first.
    with pytest.raises(ValueError, match=message):
        pyta.sma("[not json", 2, output=output)  # type: ignore[call-overload]
    with pytest.raises(ValueError, match=message):
        pyta.cci("[not json", 2, output=output)  # type: ignore[call-overload]
    with pytest.raises(ValueError, match=message):
        pyta.batch.sma(["[not json"], 2, output=output)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=message):
        pyta.batch.cci(["[not json"], 2, output=output)  # type: ignore[arg-type]


def test_pandas_target_without_pandas_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    # A None entry makes `import pandas` fail, as if it were not installed.
    monkeypatch.setitem(sys.modules, "pandas", None)
    message = "output='pandas' needs pandas, which is not installed; install PyTA's pandas extra"

    with pytest.raises(ModuleNotFoundError, match=message):
        pyta.sma("[not json", 2, output="pandas")
    with pytest.raises(ModuleNotFoundError, match=message):
        pyta.batch.cci([{"high": [1.0], "low": [1.0], "close": [1.0]}], 1, output="pandas")

    # Every other target works without pandas.
    assert pyta.sma([1.0, 2.0], 1, output="json") == '{"sma":[1.0,2.0]}'


def test_pandas_target_imports_pandas_only_when_asked() -> None:
    code = (
        "import sys, pyta; before = 'pandas' in sys.modules; "
        "pyta.sma([1.0, 2.0], 1, output='json'); json = 'pandas' in sys.modules; "
        "result = pyta.sma([1.0, 2.0], 1, output='pandas'); "
        "print(before, json, type(result).__name__)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

    assert out.stdout.strip() == "False False Series"


# --- property ------------------------------------------------------------------------------

PRICE = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)


@given(
    st.lists(PRICE, min_size=1, max_size=100),
    st.sampled_from([t for t in TARGETS if t != "pandas"]),
    st.integers(min_value=0, max_value=5),
)
def test_every_target_round_trips_values_exactly(
    values: list[float], target: str, gap: int
) -> None:
    data = [None] * gap + values
    period = len(values) // 2 + 1

    expected = pyta.sma(np.array(data, dtype=np.float64), period)
    decoded = decode(pyta.sma(data, period, output=target), target, 1, indexed=False)

    np.testing.assert_array_equal(decoded.values[0], expected)
