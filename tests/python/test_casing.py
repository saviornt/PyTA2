"""Output names: bare indicator names whose casing follows the input's columns."""

import json

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv
from pyta import _outputs as outputs_module
from pyta._outputs import OutputNames, casing

# Output names per indicator in lower, upper and title case.
LOWER = {
    "sma": ["sma"],
    "ema": ["ema"],
    "wma": ["wma"],
    "dema": ["dema"],
    "tema": ["tema"],
    "kama": ["kama"],
    "rsi": ["rsi"],
    "cci": ["cci"],
    "macd": ["macd", "macd_signal", "macd_hist"],
    "adx": ["adx", "adx_plus_di", "adx_minus_di"],
    "sar": ["sar"],
    "aroon": ["aroon_up", "aroon_down", "aroon_osc"],
    "ichimoku": [
        "ichimoku_tenkan",
        "ichimoku_kijun",
        "ichimoku_senkou_a",
        "ichimoku_senkou_b",
        "ichimoku_chikou",
    ],
    "stoch": ["stoch_k", "stoch_d"],
    "willr": ["willr"],
    "roc": ["roc"],
    "mfi": ["mfi"],
    "trix": ["trix"],
    "ultosc": ["ultosc"],
}
UPPER = {name: [n.upper() for n in names] for name, names in LOWER.items()}
TITLE = {
    "sma": ["SMA"],
    "ema": ["EMA"],
    "wma": ["WMA"],
    "dema": ["DEMA"],
    "tema": ["TEMA"],
    "kama": ["KAMA"],
    "rsi": ["RSI"],
    "cci": ["CCI"],
    "macd": ["MACD", "MACD_Signal", "MACD_Hist"],
    "adx": ["ADX", "ADX_Plus_DI", "ADX_Minus_DI"],
    "sar": ["SAR"],
    "aroon": ["Aroon_Up", "Aroon_Down", "Aroon_Osc"],
    "ichimoku": [
        "Ichimoku_Tenkan",
        "Ichimoku_Kijun",
        "Ichimoku_Senkou_A",
        "Ichimoku_Senkou_B",
        "Ichimoku_Chikou",
    ],
    "stoch": ["Stoch_K", "Stoch_D"],
    "willr": ["WILLR"],
    "roc": ["ROC"],
    "mfi": ["MFI"],
    "trix": ["TRIX"],
    "ultosc": ["ULTOSC"],
}

#: Indicators on high, low and close (and MFI's volume), cased by all the columns used.
MULTI_COLUMN = {"cci", "adx", "ichimoku", "stoch", "willr", "mfi", "ultosc"}

#: Indicators on high and low only, cased by those two columns.
HIGH_LOW = {"sar", "aroon"}

#: yfinance's column names.
YFINANCE = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def call(name: str, data: object) -> object:
    """Calls an indicator with a period that fits the 300-row fixture (defaults if none)."""
    if name in ("macd", "sar"):
        return getattr(pyta, name)(data)
    return getattr(pyta, name)(data, 10)


def dict_with(ohlcv: Ohlcv, names: list[str]) -> dict[str, list[float]]:
    """The fixture's open, high, low, close, (adj close,) volume under `names`."""
    columns = ohlcv.lists()
    values = [columns["open"], columns["high"], columns["low"], columns["close"]]
    if len(names) == 6:
        values.append([v * 0.98 for v in columns["close"]])
    values.append(columns["volume"])
    return dict(zip(names, values, strict=True))


# --- the rule -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("close",), "lower"),
        (("adj_close", "high"), "lower"),
        (("0",), "lower"),
        (("CLOSE",), "upper"),
        (("C", "H"), "upper"),
        (("Close",), "title"),
        (("Adj Close",), "title"),
        (("Adj_Close", "High"), "title"),
        # A word in capitals is title-compatible, so PyTA's own outputs chain.
        (("MACD_Signal",), "title"),
        (("SPY Close",), "title"),
        (("SPY_Close", "SPY_High"), "title"),
        (("Close", "MACD_Hist"), "title"),
        # A number (AlphaVantage's "4. close") does not count against title case.
        (("4. Close",), "title"),
        (("5. Adjusted Close", "2. High"), "title"),
        (("4. close",), "lower"),
        (("4. CLOSE",), "upper"),
        (("4. cLose",), "lower"),  # mixed
        (("SPy Close",), "lower"),  # mixed word
        ((True,), "title"),  # the casing of str(name)
        ((1,), "lower"),
        (("adj Close",), "lower"),  # mixed
        (("ClosePrice",), "lower"),  # mixed
        (("Close", "close"), "lower"),  # disagreement
        (("CLOSE", "High"), "lower"),
        ((), "lower"),
    ],
)
def test_casing_of_column_names(names: tuple[object, ...], expected: str) -> None:
    assert casing(names) == expected


def test_title_case_writes_abbreviations_upper_and_words_title() -> None:
    names = OutputNames("macd", ("macd", "macd_signal", "macd_hist"), ("macd",))

    assert names.cased(("Close",)) == ("MACD", "MACD_Signal", "MACD_Hist")
    assert names.cased(("CLOSE",)) == ("MACD", "MACD_SIGNAL", "MACD_HIST")
    assert names.cased(("close",)) == ("macd", "macd_signal", "macd_hist")
    assert names.cased(()) == ("macd", "macd_signal", "macd_hist")
    assert len(names) == 3
    assert repr(names) == "OutputNames('macd', ['macd', 'macd_signal', 'macd_hist'])"


def test_an_unabbreviated_name_is_title_case_word_by_word() -> None:
    names = OutputNames("mayer_multiple", ("mayer_multiple",), ())

    assert names.cased(("Adj Close",)) == ("Mayer_Multiple",)


def test_output_names_must_be_declared_lower_case() -> None:
    with pytest.raises(ValueError, match="output names must be lower case"):
        OutputNames("x", ("X",), ())
    with pytest.raises(ValueError, match="output names must be lower case"):
        OutputNames("x", (), ())


# --- every indicator, every casing ----------------------------------------------------------


@pytest.mark.parametrize("name", LOWER)
@pytest.mark.parametrize(
    ("columns", "single", "multi", "high_low"),
    [
        (["open", "high", "low", "close", "volume"], LOWER, LOWER, LOWER),
        (["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"], UPPER, UPPER, UPPER),
        (YFINANCE, TITLE, TITLE, TITLE),
        # Single-column indicators use only the close; CCI's and ADX's high, low and
        # close disagree; SAR's high and low disagree in the first and agree in the
        # second.
        (["open", "HIGH", "low", "Close", "volume"], TITLE, LOWER, LOWER),
        (["OPEN", "High", "Low", "CLOSE", "Volume"], UPPER, LOWER, TITLE),
        # Mixed casing in the column used.
        (["open", "high", "low", "cLOSE", "volume"], LOWER, LOWER, LOWER),
    ],
)
def test_dict_names_follow_the_columns_used(
    ohlcv: Ohlcv,
    name: str,
    columns: list[str],
    single: dict[str, list[str]],
    multi: dict[str, list[str]],
    high_low: dict[str, list[str]],
) -> None:
    result = call(name, dict_with(ohlcv, columns))
    expected = multi if name in MULTI_COLUMN else high_low if name in HIGH_LOW else single

    assert list(result) == expected[name]  # type: ignore[call-overload]


@pytest.mark.pandas
@pytest.mark.parametrize("name", LOWER)
def test_yfinance_frame_gives_title_case(ohlcv: Ohlcv, name: str) -> None:
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame(dict_with(ohlcv, YFINANCE), index=pd.DatetimeIndex(ohlcv.dates))
    frame.index.name = "Date"

    result = call(name, frame)

    assert list(result.columns) == TITLE[name]
    assert result.index.equals(frame.index)


@pytest.mark.parametrize("name", ["sma", "ema", "rsi", "macd"])
def test_the_column_picked_sets_the_casing(ohlcv: Ohlcv, name: str) -> None:
    data = dict_with(ohlcv, ["open", "high", "low", "close", "VOLUME"])

    by_default = call(name, data)
    on_volume = getattr(pyta, name)(data, *([] if name == "macd" else [10]), column="volume")

    assert list(by_default) == LOWER[name]  # type: ignore[call-overload]
    assert list(on_volume) == UPPER[name]


@pytest.mark.parametrize("name", LOWER)
@pytest.mark.parametrize(
    ("columns", "expected"),
    [(["open", "high", "low", "close", "volume"], LOWER), (YFINANCE, TITLE)],
)
def test_json_records_and_objects(
    ohlcv: Ohlcv, name: str, columns: list[str], expected: dict[str, list[str]]
) -> None:
    table = dict_with(ohlcv, columns)
    records = [dict(zip(table, row, strict=True)) for row in zip(*table.values(), strict=True)]

    as_object = json.loads(call(name, json.dumps(table)))  # type: ignore[arg-type]
    as_records = json.loads(call(name, json.dumps(records)))  # type: ignore[arg-type]

    assert list(as_object) == expected[name]
    assert all(list(row) == expected[name] for row in as_records)


@pytest.mark.parametrize("name", ["sma", "ema", "rsi"])
def test_unnamed_input_is_lower_case(ohlcv: Ohlcv, name: str) -> None:
    as_json = json.loads(call(name, json.dumps(ohlcv.close.tolist())))  # type: ignore[arg-type]

    assert isinstance(as_json, list)  # a single output keeps the array shape
    assert list(json.loads(pyta.macd(json.dumps(ohlcv.close.tolist())))) == LOWER["macd"]


def test_unnamed_multi_column_input_is_lower_case(ohlcv: Ohlcv) -> None:
    array = np.column_stack([ohlcv.high, ohlcv.low, ohlcv.close])

    assert isinstance(pyta.cci(array), np.ndarray)
    assert list(pyta.cci({"High": ohlcv.high, "Low": ohlcv.low, "Close": ohlcv.close})) == ["CCI"]


@pytest.mark.pandas
@pytest.mark.parametrize(
    ("series_name", "expected"),
    [(None, "sma"), ("close", "sma"), ("CLOSE", "SMA"), ("Close", "SMA")],
)
def test_series_name_sets_the_casing(ohlcv: Ohlcv, series_name: str | None, expected: str) -> None:
    pd = pytest.importorskip("pandas")

    assert pyta.sma(pd.Series(ohlcv.close, name=series_name), 10).name == expected


@pytest.mark.parametrize("name", LOWER)
def test_batch_cases_each_dataset_on_its_own(ohlcv: Ohlcv, name: str) -> None:
    datasets = [
        dict_with(ohlcv, YFINANCE),
        dict_with(ohlcv, ["open", "high", "low", "close", "volume"]),
    ]

    batch = getattr(pyta.batch, name)
    results = batch(datasets) if name in ("macd", "sar") else batch(datasets, 10)

    assert [list(result) for result in results] == [TITLE[name], LOWER[name]]


# --- regressions ----------------------------------------------------------------------------


def test_names_that_compare_equal_but_print_differently_are_cased_apart() -> None:
    # True == 1 == 1.0 and they hash alike, but their str() casings differ.
    names = OutputNames("sma", ("sma",), ("sma",))

    assert names.cased((True,)) == ("SMA",)
    assert names.cased((1,)) == ("sma",)
    assert names.cased((1.0,)) == ("sma",)
    assert names.cased((True, "Close")) == ("SMA",)
    assert names.cased((1, "Close")) == ("sma",)


@pytest.mark.pandas
def test_series_names_that_compare_equal_are_cased_apart(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")

    assert pyta.sma(pd.Series(ohlcv.close, name=True), 3).name == "SMA"
    assert pyta.sma(pd.Series(ohlcv.close, name=1), 3).name == "sma"


@pytest.mark.parametrize(
    "names", [(), ("Close",), ("HIGH", "LOW", "CLOSE"), ("High", "low"), ("a", "B")]
)
def test_cased_text_matches_cased_for_str_names(names: tuple[str, ...]) -> None:
    # Fresh instances, so neither call is answered from the other's memo.
    expected = OutputNames("macd", ("macd", "macd_signal"), ("macd",)).cased(names)

    assert OutputNames("macd", ("macd", "macd_signal"), ("macd",)).cased_text(names) == expected


def test_the_memo_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(outputs_module, "_MEMO_SIZE", 2)
    names = OutputNames("sma", ("sma",), ("sma",))

    cased = [names.cased((name,)) for name in ("a", "B", "Cc", "a")]

    assert cased == [("sma",), ("SMA",), ("SMA",), ("sma",)]
    assert len(names._memo) <= 2  # pyright: ignore[reportPrivateUsage]


@pytest.mark.pandas
def test_title_case_outputs_chain_as_title_case(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame(dict_with(ohlcv, YFINANCE))

    macd = pyta.macd(frame)

    assert list(macd.columns) == ["MACD", "MACD_Signal", "MACD_Hist"]
    assert pyta.sma(macd["MACD_Signal"], 5).name == "SMA"
    assert list(pyta.ema(macd[["MACD_Hist"]], 5).columns) == ["EMA"]
    assert list(pyta.rsi({"MACD_Signal": macd["MACD_Signal"].tolist()}, 5)) == ["RSI"]
