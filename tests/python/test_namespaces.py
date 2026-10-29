"""Category namespaces: `pyta.<category>.<name>` and the short-hand `pyta.<name>`.

Every style reaches the same function object, and the layout follows one
convention, so adding a category or an indicator never changes an existing import.
"""

import importlib
import operator
import pkgutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pyta
import pytest
from ohlcv_data import Ohlcv

DOCS = Path(__file__).resolve().parents[2] / "docs" / "indicators"

# Indicator name -> its category. Extend with each new indicator.
INDICATORS = {
    "sma": "trend",
    "ema": "trend",
    "macd": "trend",
    "rsi": "momentum",
    "cci": "momentum",
    "atr": "volatility",
    "stddev": "volatility",
    "bbands": "volatility",
    "donchian": "volatility",
    "keltner": "volatility",
}

# Every category subpackage, including those without indicators yet.
CATEGORIES = {"momentum", "trend", "volatility", "volume"}

# Multi-column indicators, which take full OHLCV data rather than one series.
MULTI_COLUMN = {"atr", "cci", "donchian", "keltner"}

# Documented function paths (README, docs/API.md, docs/indicators/). These must
# keep resolving: never remove an entry, only add.
DOCUMENTED_PATHS = [
    "pyta.cci",
    "pyta.momentum.cci",
    "pyta.indicators.cci",
    "pyta.indicators.momentum.cci",
    "pyta.batch.cci",
    "pyta.batch.momentum.cci",
    "pyta.sma",
    "pyta.rsi",
    "pyta.trend.sma",
    "pyta.momentum.rsi",
    "pyta.indicators.sma",
    "pyta.indicators.rsi",
    "pyta.indicators.trend.sma",
    "pyta.indicators.momentum.rsi",
    "pyta.batch.sma",
    "pyta.batch.rsi",
    "pyta.batch.trend.sma",
    "pyta.batch.momentum.rsi",
    "pyta.ema",
    "pyta.trend.ema",
    "pyta.indicators.ema",
    "pyta.indicators.trend.ema",
    "pyta.batch.ema",
    "pyta.batch.trend.ema",
    "pyta.macd",
    "pyta.trend.macd",
    "pyta.indicators.macd",
    "pyta.indicators.trend.macd",
    "pyta.batch.macd",
    "pyta.batch.trend.macd",
    "pyta.atr",
    "pyta.volatility.atr",
    "pyta.indicators.atr",
    "pyta.indicators.volatility.atr",
    "pyta.batch.atr",
    "pyta.batch.volatility.atr",
    "pyta.stddev",
    "pyta.volatility.stddev",
    "pyta.indicators.stddev",
    "pyta.indicators.volatility.stddev",
    "pyta.batch.stddev",
    "pyta.batch.volatility.stddev",
    "pyta.bbands",
    "pyta.volatility.bbands",
    "pyta.indicators.bbands",
    "pyta.indicators.volatility.bbands",
    "pyta.batch.bbands",
    "pyta.batch.volatility.bbands",
    "pyta.donchian",
    "pyta.volatility.donchian",
    "pyta.indicators.donchian",
    "pyta.indicators.volatility.donchian",
    "pyta.batch.donchian",
    "pyta.batch.volatility.donchian",
    "pyta.keltner",
    "pyta.volatility.keltner",
    "pyta.indicators.keltner",
    "pyta.indicators.volatility.keltner",
    "pyta.batch.keltner",
    "pyta.batch.volatility.keltner",
]


def _categories() -> list[str]:
    """The category subpackages found in `pyta/indicators/`."""
    return sorted(m.name for m in pkgutil.iter_modules(pyta.indicators.__path__) if m.ispkg)


def _module(category: str, name: str) -> ModuleType:
    """The indicator's own module (an attribute lookup would find the function)."""
    return importlib.import_module(f"pyta.indicators.{category}.{name}")


def _run(code: str) -> str:
    """Runs `code` in a fresh interpreter, so earlier imports do not leak in."""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.mark.parametrize(("name", "category"), INDICATORS.items())
def test_every_single_call_style_is_the_same_function(name: str, category: str) -> None:
    function = getattr(_module(category, name), name)

    assert getattr(getattr(pyta, category), name) is function
    assert getattr(getattr(pyta.indicators, category), name) is function
    assert getattr(pyta.indicators, name) is function
    assert getattr(pyta, name) is function


@pytest.mark.parametrize(("name", "category"), INDICATORS.items())
def test_every_batch_style_is_the_same_function(name: str, category: str) -> None:
    function = getattr(_module(category, name), f"{name}_batch")

    assert getattr(getattr(pyta.batch, category), name) is function
    assert getattr(pyta.batch, name) is function


@pytest.mark.parametrize(("name", "category"), INDICATORS.items())
def test_both_styles_give_the_same_results(name: str, category: str, ohlcv: Ohlcv) -> None:
    if name in MULTI_COLUMN:
        data: object = ohlcv.columns()
        datasets: list[object] = [ohlcv.lists(), {k: v[-60:] for k, v in ohlcv.columns().items()}]
    else:
        data = ohlcv.close
        datasets = [ohlcv.open.tolist(), ohlcv.close[-60:].tolist()]

    by_name = getattr(pyta, name)(data, 10)
    by_category = getattr(getattr(pyta, category), name)(data, 10)
    if name in MULTI_COLUMN:
        # Every output, in order (Donchian Channels have three).
        by_name, by_category = list(by_name.values()), list(by_category.values())
    np.testing.assert_array_equal(by_category, by_name)

    batch_by_name = getattr(pyta.batch, name)(datasets, 10)
    batch_by_category = getattr(getattr(pyta.batch, category), name)(datasets, 10)
    for got, want in zip(batch_by_category, batch_by_name, strict=True):
        if name in MULTI_COLUMN:
            got, want = list(got.values()), list(want.values())
        np.testing.assert_array_equal(got, want)


def test_known_indicators_match_the_package() -> None:
    names = set(pyta.indicators.__all__) - set(_categories())

    assert names == set(INDICATORS)
    # A category may be scaffolded before its first indicator (Sprint 11.5).
    assert set(INDICATORS.values()) <= set(_categories())
    assert set(_categories()) == CATEGORIES


@pytest.mark.parametrize("category", _categories())
def test_category_follows_the_convention(category: str) -> None:
    subpackage = importlib.import_module(f"pyta.indicators.{category}")
    modules = sorted(m.name for m in pkgutil.iter_modules(subpackage.__path__))

    # One module per indicator, each re-exported by the subpackage.
    assert sorted(subpackage.__all__) == modules
    # The top-level and batch namespaces list exactly the subpackage's names.
    assert sorted(importlib.import_module(f"pyta.{category}").__all__) == modules
    assert sorted(importlib.import_module(f"pyta.batch.{category}").__all__) == modules
    # The category is listed by every parent namespace.
    for parent in (pyta, pyta.indicators, pyta.batch):
        assert category in parent.__all__
    # The category has its docs folder; each indicator its user doc, in no other category.
    assert (DOCS / category).is_dir(), category
    for name in modules:
        assert (DOCS / category / f"{name}.md").is_file(), f"{category}/{name}.md"
        assert INDICATORS[name] == category


@pytest.mark.parametrize("namespace", [pyta, pyta.indicators, pyta.batch])
def test_namespace_exports_are_sorted(namespace: ModuleType) -> None:
    assert namespace.__all__ == sorted(namespace.__all__)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("import pyta.trend; print(pyta.trend.sma([1.0, 2.0], 2))", "[nan, 1.5]"),
        ("from pyta.momentum import rsi; print(rsi([1.0, 2.0], 1))", "[nan, 100.0]"),
        ("from pyta.batch.momentum import rsi; print(rsi([[1.0, 2.0]], 1))", "[[nan, 100.0]]"),
        # `import a.b.sma as m` would bind the function `sma`, so read the module from sys.modules.
        (
            "import sys, pyta.indicators.momentum.rsi; "
            "print(sys.modules['pyta.indicators.momentum.rsi'].rsi_batch([[1.0, 2.0]], 1))",
            "[[nan, 100.0]]",
        ),
    ],
)
def test_category_imports_work_in_a_fresh_interpreter(code: str, expected: str) -> None:
    assert _run(code) == expected


@pytest.mark.parametrize("category", sorted(CATEGORIES))
def test_category_import_does_not_load_pandas(category: str) -> None:
    code = f"import sys, pyta.{category}, pyta.batch.{category}; print('pandas' in sys.modules)"

    assert _run(code) == "False"


@pytest.mark.parametrize("path", DOCUMENTED_PATHS)
def test_documented_function_paths_resolve(path: str) -> None:
    function = operator.attrgetter(path.removeprefix("pyta."))(pyta)

    assert callable(function)
