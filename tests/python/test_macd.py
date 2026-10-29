"""MACD: three outputs in every container, warm-ups, parameters, errors and batch."""

import json

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

NAMES = ["macd", "macd_signal", "macd_hist"]


def _ema_from(values: NDArray[np.float64], period: int, end: int) -> NDArray[np.float64]:
    """EMA seeded with the mean of the `period` values ending at index `end`."""
    out = np.full(values.shape[0], np.nan)
    k = 2.0 / (period + 1)
    out[end] = values[end - period + 1 : end + 1].mean()
    for i in range(end + 1, values.shape[0]):
        out[i] = out[i - 1] + k * (values[i] - out[i - 1])
    return out


def reference_macd(
    prices: NDArray[np.float64], fast: int, slow: int, signal: int
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """TA-Lib's MACD written out in Python: both EMAs start at row `slow - 1`."""
    line = _ema_from(prices, fast, slow - 1) - _ema_from(prices, slow, slow - 1)
    sig = np.full(prices.shape[0], np.nan)
    sig[slow - 1 :] = _ema_from(line[slow - 1 :], signal, signal - 1)
    return line, sig, line - sig


def assert_outputs(got: object, want: tuple[NDArray[np.float64], ...]) -> None:
    for got_one, want_one in zip(got, want, strict=True):  # type: ignore[call-overload]
        np.testing.assert_array_equal(np.asarray(got_one, dtype=np.float64), want_one)


# --- values and warm-up ---------------------------------------------------------------------


@pytest.mark.parametrize(("fast", "slow", "signal"), [(12, 26, 9), (5, 35, 5), (2, 3, 1)])
def test_matches_a_python_reference_on_real_prices(
    ohlcv: Ohlcv, fast: int, slow: int, signal: int
) -> None:
    result = pyta.macd(ohlcv.close, fast, slow, signal)

    for got, want in zip(result, reference_macd(ohlcv.close, fast, slow, signal), strict=True):
        np.testing.assert_allclose(got, want, rtol=1e-9, atol=1e-9, equal_nan=True)


@pytest.mark.parametrize(("fast", "slow", "signal"), [(12, 26, 9), (3, 10, 4), (2, 2, 1)])
def test_each_output_has_its_own_warm_up(ohlcv: Ohlcv, fast: int, slow: int, signal: int) -> None:
    line, sig, hist = pyta.macd(ohlcv.close, fast, slow, signal)

    assert np.isnan(line[: slow - 1]).all()
    assert np.isfinite(line[slow - 1 :]).all()
    for values in (sig, hist):
        warm_up = slow + signal - 2
        assert np.isnan(values[:warm_up]).all()
        assert np.isfinite(values[warm_up:]).all()


def test_defaults_are_twelve_twenty_six_nine(ohlcv: Ohlcv) -> None:
    assert_outputs(pyta.macd(ohlcv.close), pyta.macd(ohlcv.close, 12, 26, 9))


def test_hist_is_macd_minus_signal(ohlcv: Ohlcv) -> None:
    line, sig, hist = pyta.macd(ohlcv.close)

    np.testing.assert_array_equal(hist, line - sig)


def test_fast_above_slow_gives_the_same_as_swapped(ohlcv: Ohlcv) -> None:
    assert_outputs(pyta.macd(ohlcv.close, 26, 12, 9), pyta.macd(ohlcv.close, 12, 26, 9))


def test_fast_equal_to_slow_gives_zero(ohlcv: Ohlcv) -> None:
    for values in pyta.macd(ohlcv.close, 10, 10, 3):
        assert (values[~np.isnan(values)] == 0.0).all()


def test_flat_prices_give_zero() -> None:
    for values in pyta.macd(np.full(60, 42.0)):
        assert (values[~np.isnan(values)] == 0.0).all()


def test_needs_slow_plus_signal_minus_one_values() -> None:
    pyta.macd(np.arange(1.0, 35.0))  # 34 values: every output has one value

    with pytest.raises(ValueError, match="at least 34 values are required, got 33"):
        pyta.macd(np.arange(1.0, 34.0))


def test_leading_nan_shifts_every_output_alike(ohlcv: Ohlcv) -> None:
    sma = pyta.sma(ohlcv.close, period=20)  # 19 leading NaN

    chained = pyta.macd(sma)
    direct = pyta.macd(sma[19:])

    for got, want, warm_up in zip(chained, direct, (25, 33, 33), strict=True):
        assert got.shape == sma.shape
        assert np.isnan(got[: 19 + warm_up]).all()
        np.testing.assert_array_equal(got[19:], want)


# --- parameters -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"fast": 1}, "fast must be between 2 and 2147483647, got 1"),
        ({"fast": 0}, "fast must be between 2 and 2147483647, got 0"),
        ({"slow": 1}, "slow must be between 2 and 2147483647, got 1"),
        ({"slow": 2**31}, "slow must be between 2 and 2147483647, got 2147483648"),
        ({"signal": 0}, "signal must be between 1 and 2147483647, got 0"),
        ({"signal": -1}, "signal must be between 1 and 2147483647, got -1"),
    ],
)
def test_out_of_range_parameters_name_the_parameter(kwargs: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        pyta.macd(np.arange(1.0, 100.0), **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"fast": 2.5}, "fast must be an integer, got float"),
        ({"slow": "26"}, "slow must be an integer, got str"),
        ({"signal": True}, "signal must be an integer, not bool"),
        ({"fast": None}, "fast must be an integer, got NoneType"),
    ],
)
def test_wrong_parameter_types_name_the_parameter(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(TypeError, match=message):
        pyta.macd(np.arange(1.0, 100.0), **kwargs)  # type: ignore[arg-type]


def test_numpy_integers_are_accepted(ohlcv: Ohlcv) -> None:
    assert_outputs(
        pyta.macd(ohlcv.close, np.int64(12), np.int32(26), np.uint8(9)),  # type: ignore[arg-type]
        pyta.macd(ohlcv.close),
    )


def test_rejects_columns_and_bad_column() -> None:
    with pytest.raises(ValueError, match="macd uses one column"):
        pyta.macd({"close": [1.0]}, columns=["close"])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="column must be a str or None, got int"):
        pyta.macd({"close": [1.0]}, column=3)  # type: ignore[arg-type]


# --- containers -----------------------------------------------------------------------------


@pytest.fixture
def want(ohlcv: Ohlcv) -> tuple[NDArray[np.float64], ...]:
    return tuple(pyta.macd(ohlcv.close))


@pytest.mark.parametrize(
    ("convert", "kind"),
    [
        (lambda a: a, np.ndarray),
        (lambda a: a.tolist(), list),
        (lambda a: tuple(a.tolist()), tuple),
    ],
)
def test_one_series_gives_a_tuple_of_its_own_kind(
    ohlcv: Ohlcv, want: tuple[NDArray[np.float64], ...], convert: object, kind: type
) -> None:
    result = pyta.macd(convert(ohlcv.close))  # type: ignore[operator]

    assert isinstance(result, tuple)
    assert len(result) == 3
    assert all(type(output) is kind for output in result)
    assert_outputs(result, want)


@pytest.mark.pandas
def test_series_gives_a_tuple_of_named_series(
    ohlcv: Ohlcv, want: tuple[NDArray[np.float64], ...]
) -> None:
    pd = pytest.importorskip("pandas")
    index = pd.DatetimeIndex(ohlcv.dates)

    for name, names in (
        (None, NAMES),
        ("close", NAMES),
        ("Close", ["MACD", "MACD_Signal", "MACD_Hist"]),
    ):
        result = pyta.macd(pd.Series(ohlcv.close, index=index, name=name))

        assert isinstance(result, tuple)
        assert [output.name for output in result] == names
        assert all(output.index.equals(index) for output in result)
        assert_outputs(result, want)


@pytest.mark.pandas
def test_dataframe_gives_three_columns_and_keeps_its_index(
    ohlcv: Ohlcv, want: tuple[NDArray[np.float64], ...]
) -> None:
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame(ohlcv.columns(), index=pd.DatetimeIndex(ohlcv.dates))

    result = pyta.macd(frame)

    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == NAMES
    assert result.index.equals(frame.index)
    assert_outputs([result[name] for name in NAMES], want)


@pytest.mark.parametrize(
    ("convert", "kind"),
    [(lambda a: a.tolist(), list), (lambda a: a, np.ndarray), (lambda a: tuple(a), tuple)],
)
def test_dict_gives_one_key_per_output_in_the_column_type(
    ohlcv: Ohlcv, want: tuple[NDArray[np.float64], ...], convert: object, kind: type
) -> None:
    data = {"open": ohlcv.open.tolist(), "close": convert(ohlcv.close)}  # type: ignore[operator]

    result = pyta.macd(data)

    assert list(result) == NAMES
    assert all(type(result[name]) is kind for name in NAMES)
    assert_outputs([result[name] for name in NAMES], want)


@pytest.mark.pandas
def test_dict_of_series_gives_named_series(
    ohlcv: Ohlcv, want: tuple[NDArray[np.float64], ...]
) -> None:
    pd = pytest.importorskip("pandas")
    close = pd.Series(ohlcv.close, index=pd.DatetimeIndex(ohlcv.dates))

    result = pyta.macd({"close": close})

    assert [result[name].name for name in NAMES] == NAMES
    assert all(result[name].index.equals(close.index) for name in NAMES)


def _nulls(values: NDArray[np.float64]) -> list[float | None]:
    return [None if np.isnan(v) else float(v) for v in values]


@pytest.mark.parametrize("as_bytes", [False, True])
def test_json_shapes(ohlcv: Ohlcv, want: tuple[NDArray[np.float64], ...], as_bytes: bool) -> None:
    def encode(obj: object) -> str | bytes:
        text = json.dumps(obj)
        return text.encode() if as_bytes else text

    closes = ohlcv.close.tolist()
    records = [{"date": d, "close": c} for d, c in zip(ohlcv.dates, closes, strict=True)]
    expected = {name: _nulls(values) for name, values in zip(NAMES, want, strict=True)}

    for data, shape in (
        (encode(ohlcv.close.tolist()), "object"),  # an array of numbers gives an object
        (encode({"close": ohlcv.close.tolist()}), "object"),
        (encode(records), "records"),
    ):
        result = pyta.macd(data)

        assert isinstance(result, bytes if as_bytes else str)
        assert "NaN" not in (result.decode() if isinstance(result, bytes) else result)
        parsed = json.loads(result)
        if shape == "records":
            assert all(list(row) == NAMES for row in parsed)
            assert {name: [row[name] for row in parsed] for name in NAMES} == expected
        else:
            assert list(parsed) == NAMES
            assert parsed == expected


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets: list[object] = [
        ohlcv.close.tolist(),
        ohlcv.close[:20].tolist(),  # too short: the native call fails for this one only
        "{not json",  # Python rejects this one before the native call
        {"close": ohlcv.close[-60:]},
    ]

    results = pyta.batch.macd(datasets, 5, 35, 5)

    assert_outputs(results[0], pyta.macd(ohlcv.close.tolist(), 5, 35, 5))
    assert isinstance(results[1], ValueError)
    assert "at least 39 values" in str(results[1])
    assert isinstance(results[2], ValueError)
    assert "invalid JSON" in str(results[2])
    assert list(results[3]) == NAMES
    assert_outputs([results[3][name] for name in NAMES], pyta.macd(ohlcv.close[-60:], 5, 35, 5))


def test_batch_mapping_keeps_keys(ohlcv: Ohlcv) -> None:
    results = pyta.batch.macd({"b": ohlcv.close, "a": ohlcv.open})

    assert list(results) == ["b", "a"]
    assert_outputs(results["a"], pyta.macd(ohlcv.open))


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [({"fast": 1}, ValueError), ({"signal": 0}, ValueError), ({"slow": 2.0}, TypeError)],
)
def test_batch_shared_parameters_raise_for_the_whole_call(
    ohlcv: Ohlcv, kwargs: dict[str, object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        pyta.batch.macd([ohlcv.close, ohlcv.open], **kwargs)  # type: ignore[arg-type]


def test_batch_fast_above_slow_is_swapped(ohlcv: Ohlcv) -> None:
    (swapped,) = pyta.batch.macd([ohlcv.close], 26, 12, 9)

    assert_outputs(swapped, pyta.macd(ohlcv.close))
