"""Column roles: aliases, separators, and the per-indicator default column."""

import json

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv, rolling_mean
from pyta._validation import ADJ_CLOSE, CLOSE, HIGH, LOW, OPEN, VOLUME, normalize

CLOSES = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
OTHER = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]


def values_of(prepared) -> list[float]:
    return prepared.values.tolist()


@pytest.mark.parametrize(
    ("role", "names"),
    [
        (OPEN, ["open", "Open", "OPENING", "open_price", "Opening Price", "o"]),
        (HIGH, ["high", "High", "highest", "high-price", "Highest Price", "H"]),
        (LOW, ["low", "LOW", "lowest", "low_price", "Lowest Price", "l"]),
        (CLOSE, ["close", " Close ", "closing", "close_price", "Closing Price", "C"]),
        (
            ADJ_CLOSE,
            ["adj_close", "Adj Close", "adj.close", "adjclose", "Adjusted Close", "adjusted-close"],
        ),
        (VOLUME, ["volume", "Volume", "volumes", "vol", "VOL", "v"]),
    ],
)
def test_every_alias_of_a_role_is_found_by_the_role(role, names) -> None:
    for name in names:
        frame = {"zzz": OTHER, name: CLOSES}

        assert values_of(normalize(frame, None, role)) == CLOSES, name
        assert values_of(normalize(frame, role, role)) == CLOSES, name


def test_requested_name_matches_any_alias_of_its_role() -> None:
    frame = {"Adj Close": CLOSES, "Close": OTHER}

    assert values_of(normalize(frame, "adjusted_close", CLOSE)) == CLOSES
    assert values_of(normalize(frame, "closing", CLOSE)) == OTHER


def test_exact_spelling_wins_over_an_alias() -> None:
    assert values_of(normalize({"h": CLOSES, "high": OTHER}, "h", CLOSE)) == CLOSES


def test_close_never_falls_back_to_the_adjusted_close() -> None:
    frame = {"Adj Close": CLOSES, "Volume": OTHER}

    with pytest.raises(ValueError, match="no 'close' column found"):
        normalize(frame, None, CLOSE)

    assert values_of(normalize(frame, None, ADJ_CLOSE)) == CLOSES


def test_default_column_is_the_one_the_caller_names() -> None:
    frame = {"open": OTHER, "high": CLOSES, "close": OTHER}

    assert values_of(normalize(frame, None, HIGH)) == CLOSES
    assert values_of(normalize(frame, None, CLOSE)) == OTHER

    with pytest.raises(ValueError, match="no 'low' column found"):
        normalize(frame, None, LOW)


def test_explicit_column_beats_the_default() -> None:
    frame = {"high": CLOSES, "close": OTHER}

    assert values_of(normalize(frame, "close", HIGH)) == OTHER


def test_a_single_column_is_used_whatever_its_name() -> None:
    assert values_of(normalize({"px": CLOSES}, None, HIGH)) == CLOSES

    with pytest.raises(ValueError, match="not found"):
        normalize({"px": CLOSES}, "close", HIGH)


def test_explicit_column_must_be_a_known_role_even_if_the_input_has_it() -> None:
    with pytest.raises(ValueError, match="not a recognized column name"):
        normalize({"px": CLOSES, "vol_usd": OTHER}, "px", CLOSE)

    with pytest.raises(ValueError, match="adj_close"):
        normalize({"px": CLOSES}, "price", CLOSE)


def test_unrecognized_names_still_work_when_the_input_has_one_column() -> None:
    # Chaining: an indicator's own output column ("sma") feeds the next call.
    chained = pyta.rsi(pyta.sma({"close": [float(i) for i in range(1, 12)]}, period=3), period=2)

    assert list(chained) == ["rsi"]


def test_names_that_differ_only_in_separators_are_ambiguous() -> None:
    with pytest.raises(ValueError, match="same after"):
        normalize({"Adj_Close": CLOSES, "adj close": OTHER}, None, CLOSE)


def test_unrelated_names_are_not_aliases() -> None:
    with pytest.raises(ValueError, match="not found"):
        normalize({"closed": CLOSES, "x": OTHER}, "close", CLOSE)


def test_indicators_use_the_adjusted_close_on_request() -> None:
    frame = {"Close": OTHER, "Adj Close": CLOSES}

    result = pyta.sma(frame, period=2, column="adj close")

    np.testing.assert_array_equal(result["SMA"], [np.nan, 1.5, 2.5, 3.5, 4.5, 5.5])


def test_indicators_find_short_ohlcv_json_keys() -> None:
    text = json.dumps({"o": OTHER, "h": OTHER, "l": OTHER, "c": CLOSES, "v": OTHER})

    result = json.loads(pyta.sma(text, period=2))

    assert result["sma"] == [None, 1.5, 2.5, 3.5, 4.5, 5.5]


def test_batch_applies_aliases_to_every_dataset() -> None:
    results = pyta.batch.sma(
        [{"Adj Close": CLOSES}, {"adjusted_close": CLOSES, "Close": OTHER}],
        period=2,
        column="adjclose",
    )

    for result, name in zip(results, ["SMA", "sma"], strict=True):
        np.testing.assert_array_equal(result[name], [np.nan, 1.5, 2.5, 3.5, 4.5, 5.5])


# --- a full real OHLCV input ----------------------------------------------------------------


def test_full_ohlcv_dict_uses_close_by_default(ohlcv: Ohlcv) -> None:
    result = pyta.sma({"date": ohlcv.dates, **ohlcv.lists()}, period=20)

    np.testing.assert_allclose(
        result["sma"], rolling_mean(ohlcv.close, 20), rtol=1e-12, equal_nan=True
    )


@pytest.mark.parametrize(
    ("column", "role"),
    [("open", OPEN), ("High", HIGH), ("low", LOW), ("Close", CLOSE), ("vol", VOLUME)],
)
def test_full_ohlcv_dict_gives_each_role_on_request(ohlcv: Ohlcv, column: str, role: str) -> None:
    result = pyta.sma(ohlcv.columns(), period=20, column=column)

    np.testing.assert_allclose(
        result["sma"], rolling_mean(ohlcv.columns()[role], 20), rtol=1e-12, equal_nan=True
    )


@pytest.mark.pandas
def test_provider_style_dataframe_finds_each_role(ohlcv: Ohlcv) -> None:
    pd = pytest.importorskip("pandas")
    # Spelled the way yfinance returns them, including an adjusted close.
    frame = pd.DataFrame(
        {
            "Open": ohlcv.open,
            "High": ohlcv.high,
            "Low": ohlcv.low,
            "Close": ohlcv.close,
            "Adj Close": ohlcv.close * 0.98,
            "Volume": ohlcv.volume,
        },
        index=pd.DatetimeIndex(ohlcv.dates),
    )

    by_default = pyta.rsi(frame)
    adjusted = pyta.sma(frame, period=20, column="adjusted close")

    np.testing.assert_array_equal(by_default["RSI"], pyta.rsi(ohlcv.close))
    np.testing.assert_allclose(
        adjusted["SMA"], rolling_mean(ohlcv.close * 0.98, 20), rtol=1e-12, equal_nan=True
    )
