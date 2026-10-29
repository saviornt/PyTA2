"""Bollinger Bands: three outputs, numerics, parameters, errors, containers and batch."""

import json
import math

import numpy as np
import pyta
import pytest
from numpy.typing import NDArray
from ohlcv_data import Ohlcv

NAMES = ["bbands_upper", "bbands_middle", "bbands_lower"]


def reference_bbands(
    values: NDArray[np.float64], period: int, k: float
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """SMA and population deviation of each window, two passes, in NumPy."""
    windows = np.lib.stride_tricks.sliding_window_view(values, period)
    middle = np.full(values.shape[0], np.nan)
    width = np.full(values.shape[0], np.nan)
    middle[period - 1 :] = windows.mean(axis=1)
    width[period - 1 :] = k * windows.std(axis=1)
    return middle + width, middle, middle - width


def assert_outputs(got: object, want: tuple[NDArray[np.float64], ...]) -> None:
    for got_one, want_one in zip(got, want, strict=True):  # type: ignore[call-overload]
        np.testing.assert_array_equal(np.asarray(got_one, dtype=np.float64), want_one)


# --- values and warm-up ---------------------------------------------------------------------


def test_known_values() -> None:
    # Windows of 2: means 2, 5, 7.5; deviations 1, 2, 0.5 (half of each gap), times k = 2.
    upper, middle, lower = pyta.bbands([1.0, 3.0, 7.0, 8.0], period=2, k=2.0)

    assert all(math.isnan(band[0]) for band in (upper, middle, lower))
    assert upper[1:] == [4.0, 9.0, 8.5]
    assert middle[1:] == [2.0, 5.0, 7.5]
    assert lower[1:] == [0.0, 1.0, 6.5]


@pytest.mark.parametrize(("period", "k"), [(2, 1.0), (20, 2.0), (50, 2.5), (200, 0.5)])
def test_matches_numpy_on_real_closes(ohlcv: Ohlcv, period: int, k: float) -> None:
    result = pyta.bbands(ohlcv.close, period=period, k=k)

    for got, want in zip(result, reference_bbands(ohlcv.close, period, k), strict=True):
        np.testing.assert_allclose(got, want, rtol=1e-12, equal_nan=True)


@pytest.mark.parametrize("period", [2, 20, 100])
def test_all_outputs_share_one_warm_up(ohlcv: Ohlcv, period: int) -> None:
    for band in pyta.bbands(ohlcv.close, period=period):
        assert band.shape == ohlcv.close.shape
        assert np.isnan(band[: period - 1]).all()
        assert np.isfinite(band[period - 1 :]).all()


def test_defaults_are_period_twenty_and_k_two(ohlcv: Ohlcv) -> None:
    assert_outputs(pyta.bbands(ohlcv.close), pyta.bbands(ohlcv.close, period=20, k=2.0))


def test_middle_is_the_sma_and_the_bands_are_k_stddevs_from_it(ohlcv: Ohlcv) -> None:
    upper, middle, lower = pyta.bbands(ohlcv.close, period=20, k=2.0)
    width = pyta.stddev(ohlcv.close, period=20, k=2.0)

    np.testing.assert_allclose(middle, pyta.sma(ohlcv.close, period=20), rtol=1e-12)
    np.testing.assert_array_equal(upper, middle + width)
    np.testing.assert_array_equal(lower, middle - width)


def test_flat_prices_give_three_equal_bands() -> None:
    for level in (105.0, 101.37, 0.1):
        upper, middle, lower = pyta.bbands(np.full(30, level), period=7)

        np.testing.assert_array_equal(upper[6:], middle[6:])
        np.testing.assert_array_equal(lower[6:], middle[6:])


def test_needs_at_least_period_values() -> None:
    pyta.bbands([1.0, 2.0, 3.0, 4.0], period=4)

    with pytest.raises(ValueError, match=r"period \(5\) exceeds the series length \(4\)"):
        pyta.bbands([1.0, 2.0, 3.0, 4.0], period=5)


def test_leading_nan_shifts_every_output_alike(ohlcv: Ohlcv) -> None:
    sma = pyta.sma(ohlcv.close, period=10)  # 9 leading NaN

    chained = pyta.bbands(sma, period=5)
    direct = pyta.bbands(sma[9:], period=5)

    for got, want in zip(chained, direct, strict=True):
        assert got.shape == sma.shape
        assert np.isnan(got[:13]).all()
        np.testing.assert_array_equal(got[9:], want)


# --- parameters -----------------------------------------------------------------------------


@pytest.mark.parametrize("period", [0, 1, -3, 2**31])
def test_period_must_be_at_least_two(period: int) -> None:
    with pytest.raises(ValueError, match="period must be between 2 and"):
        pyta.bbands([1.0, 2.0, 3.0], period=period)


@pytest.mark.parametrize("period", ["5", 2.5, True, None])
def test_period_must_be_an_integer(period: object) -> None:
    with pytest.raises(TypeError, match="period must be an integer"):
        pyta.bbands([1.0, 2.0, 3.0], period=period)  # type: ignore[arg-type]


@pytest.mark.parametrize("k", [0, 0.0, -1.0, math.inf, math.nan, -math.inf])
def test_k_must_be_a_finite_number_above_zero(k: float) -> None:
    with pytest.raises(ValueError, match="k must be a finite number greater than 0"):
        pyta.bbands([1.0, 2.0, 3.0], period=2, k=k)


@pytest.mark.parametrize("k", ["2", True, None])
def test_k_must_be_a_number(k: object) -> None:
    with pytest.raises(TypeError, match="k must be a number"):
        pyta.bbands([1.0, 2.0, 3.0], period=2, k=k)  # type: ignore[arg-type]


def test_k_accepts_ints_and_numpy_numbers(ohlcv: Ohlcv) -> None:
    want = pyta.bbands(ohlcv.close, period=10, k=2.0)

    assert_outputs(pyta.bbands(ohlcv.close, period=10, k=2), want)
    assert_outputs(pyta.bbands(ohlcv.close, period=10, k=np.float64(2.0)), want)
    assert_outputs(pyta.bbands(ohlcv.close, period=10, k=np.int64(2)), want)  # type: ignore[arg-type]


def test_rejects_columns_and_bad_column() -> None:
    with pytest.raises(ValueError, match="bbands uses one column"):
        pyta.bbands({"close": [1.0, 2.0]}, columns=["close"])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="column must be a str or None, got int"):
        pyta.bbands({"close": [1.0, 2.0]}, column=3)  # type: ignore[arg-type]


# --- containers -----------------------------------------------------------------------------


@pytest.fixture
def want(ohlcv: Ohlcv) -> tuple[NDArray[np.float64], ...]:
    return tuple(pyta.bbands(ohlcv.close))


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
    result = pyta.bbands(convert(ohlcv.close))  # type: ignore[operator]

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
        ("CLOSE", ["BBANDS_UPPER", "BBANDS_MIDDLE", "BBANDS_LOWER"]),
        ("Close", ["BBANDS_Upper", "BBANDS_Middle", "BBANDS_Lower"]),
    ):
        result = pyta.bbands(pd.Series(ohlcv.close, index=index, name=name))

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

    result = pyta.bbands(frame)

    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == NAMES
    assert result.index.equals(frame.index)
    assert_outputs([result[name] for name in NAMES], want)


def test_dict_gives_one_key_per_output_and_column_selects_the_role(ohlcv: Ohlcv) -> None:
    data = {"open": ohlcv.open.tolist(), "close": ohlcv.close.tolist()}

    result = pyta.bbands(data, period=10)
    from_open = pyta.bbands(data, period=10, column="open")

    assert list(result) == NAMES
    assert all(type(result[name]) is list for name in NAMES)
    assert_outputs([result[name] for name in NAMES], pyta.bbands(ohlcv.close, period=10))
    assert_outputs([from_open[name] for name in NAMES], pyta.bbands(ohlcv.open, period=10))


def _nulls(values: NDArray[np.float64]) -> list[float | None]:
    return [None if np.isnan(v) else float(v) for v in values]


def test_json_array_gives_an_object_keyed_by_output(
    ohlcv: Ohlcv, want: tuple[NDArray[np.float64], ...]
) -> None:
    result = pyta.bbands(json.dumps(ohlcv.close.tolist()))

    parsed = json.loads(result)
    assert list(parsed) == NAMES
    assert parsed == {name: _nulls(values) for name, values in zip(NAMES, want, strict=True)}


def test_output_converts_to_another_container(
    ohlcv: Ohlcv, want: tuple[NDArray[np.float64], ...]
) -> None:
    result = pyta.bbands(ohlcv.close.tolist(), output="dict")

    assert list(result) == NAMES
    assert_outputs([result[name] for name in NAMES], want)


# --- batch ----------------------------------------------------------------------------------


def test_batch_matches_single_calls_and_keeps_failures_in_place(ohlcv: Ohlcv) -> None:
    datasets: list[object] = [
        ohlcv.close.tolist(),
        ohlcv.close[:10].tolist(),  # too short: the native call fails for this one only
        "{not json",  # Python rejects this one before the native call
        {"close": ohlcv.close[-60:]},
    ]

    results = pyta.batch.bbands(datasets, 20, 2.0)

    assert_outputs(results[0], pyta.bbands(ohlcv.close.tolist()))
    assert isinstance(results[1], ValueError)
    assert "exceeds the series length" in str(results[1])
    assert isinstance(results[2], ValueError)
    assert "invalid JSON" in str(results[2])
    assert list(results[3]) == NAMES
    assert_outputs([results[3][name] for name in NAMES], pyta.bbands(ohlcv.close[-60:]))


def test_batch_mapping_keeps_keys(ohlcv: Ohlcv) -> None:
    results = pyta.batch.bbands({"b": ohlcv.close, "a": ohlcv.open}, period=10, k=1.5)

    assert list(results) == ["b", "a"]
    assert_outputs(results["a"], pyta.bbands(ohlcv.open, period=10, k=1.5))


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [({"period": 1}, ValueError), ({"k": -1.0}, ValueError), ({"k": "2"}, TypeError)],
)
def test_batch_shared_parameters_raise_for_the_whole_call(
    ohlcv: Ohlcv, kwargs: dict[str, object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        pyta.batch.bbands([ohlcv.close, ohlcv.open], **kwargs)  # type: ignore[arg-type]
