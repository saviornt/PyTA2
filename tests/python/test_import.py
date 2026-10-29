"""The import surface: what `import pyta` loads and exports."""

import subprocess
import sys
import typing

import pyta
import pytest
from pyta.indicators.momentum.rsi import rsi_batch
from pyta.indicators.trend.sma import sma_batch


def _run(code: str) -> str:
    """Runs `code` in a fresh interpreter, so earlier imports do not leak in."""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def test_import_does_not_load_pandas() -> None:
    assert _run("import sys, pyta; print('pandas' in sys.modules)") == "False"


def test_import_works_when_pandas_is_missing() -> None:
    # A None entry makes `import pandas` raise ImportError, as if not installed.
    code = "import sys; sys.modules['pandas'] = None; import pyta; print(pyta.sma([1.0, 2.0], 2))"

    assert _run(code) == "[nan, 1.5]"


def test_top_level_exports() -> None:
    assert sorted(pyta.__all__) == [
        "Output",
        "atr",
        "batch",
        "cci",
        "ema",
        "indicators",
        "macd",
        "momentum",
        "rsi",
        "sma",
        "stddev",
        "trend",
        "volatility",
        "volume",
    ]


@pytest.mark.parametrize(
    "module",
    [
        pyta,
        pyta.indicators,
        pyta.batch,
        pyta.trend,
        pyta.momentum,
        pyta.batch.trend,
        pyta.batch.momentum,
        pyta.volatility,
        pyta.volume,
        pyta.batch.volatility,
        pyta.batch.volume,
    ],
)
def test_every_exported_name_exists(module: object) -> None:
    for name in module.__all__:  # type: ignore[attr-defined]
        assert hasattr(module, name), name


def test_indicator_and_batch_namespaces_list_the_same_indicators() -> None:
    expected = [
        "atr",
        "cci",
        "ema",
        "macd",
        "momentum",
        "rsi",
        "sma",
        "stddev",
        "trend",
        "volatility",
        "volume",
    ]

    assert sorted(pyta.indicators.__all__) == sorted(pyta.batch.__all__) == expected


def test_short_names_are_the_indicator_functions() -> None:
    assert pyta.sma is pyta.indicators.sma
    assert pyta.rsi is pyta.indicators.rsi


def test_batch_names_are_the_batch_functions() -> None:
    assert pyta.batch.sma is sma_batch
    assert pyta.batch.rsi is rsi_batch


def test_output_type_lists_every_target() -> None:
    assert typing.get_args(pyta.Output.__value__) == pyta._export.TARGETS  # pyright: ignore[reportPrivateUsage]
