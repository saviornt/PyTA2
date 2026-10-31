"""PyTA against TA-Lib, each called the way its documentation shows for everyday use.

Two comparisons, both timed with `timeit` over the whole call (input handling and output wrapping
included), best of `--repeat` runs, the two libraries alternating within each repeat:

- single: one dataset per call, `talib.<NAME>(...)` against `pyta.<name>(...)`;
- batch: many datasets. TA-Lib has no batch call, so its form is a list comprehension calling
  `talib.<NAME>` per dataset; PyTA's is one `pyta.batch.<name>(...)` call over the list.

Each runs on float64 NumPy arrays (TA-Lib takes one array per input, PyTA a dict of named arrays)
and on yFinance-shaped pandas DataFrames (TA-Lib takes the frame's columns, PyTA the frame). The
data is a seeded random walk, the same for both libraries. Indicators with several TA-Lib calls
(ADX with PLUS_DI and MINUS_DI, AROON with AROONOSC) time every call that produces PyTA's outputs.

Run with the `bench` extra installed (scripts/setup.sh --bench):

    .venv/bin/python benchmarks/compare_talib.py [--quick] [--indicator NAME ...]

The report is printed and written to results/compare_talib_<timestamp>.md.
"""

import argparse
import math
import platform
import sys
import timeit
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyta
import talib

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
SINGLE_ROWS = (100, 10_000, 1_000_000)
BATCH_SHAPES = ((10, 1_000), (100, 100), (100, 10_000), (1_000, 1_000))  # (datasets, rows)
ROLES = ("open", "high", "low", "close", "volume")
FRAME_COLUMNS = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
NO_TALIB = ("ichimoku", "keltner", "donchian", "cmf", "vwap", "vroc")

type Arrays = dict[str, np.ndarray]
type Dataset = Arrays | pd.DataFrame


@dataclass(frozen=True, slots=True)
class Pair:
    """One indicator: PyTA's name and parameters, TA-Lib's calls giving the same outputs."""

    name: str
    params: dict[str, Any]
    inputs: tuple[str, ...]  # roles, in TA-Lib's argument order
    talib: Callable[..., Any]  # takes the input columns positionally
    order: tuple[int, ...] = ()  # TA-Lib output positions in PyTA's output order


def _adx(h: Any, lo: Any, c: Any) -> tuple[Any, Any, Any]:
    return (
        talib.ADX(h, lo, c, timeperiod=14),
        talib.PLUS_DI(h, lo, c, timeperiod=14),
        talib.MINUS_DI(h, lo, c, timeperiod=14),
    )


def _aroon(h: Any, lo: Any) -> tuple[Any, Any, Any]:
    down, up = talib.AROON(h, lo, timeperiod=14)
    return up, down, talib.AROONOSC(h, lo, timeperiod=14)


HLC = ("high", "low", "close")
HLCV = ("high", "low", "close", "volume")
PAIRS = (
    Pair("sma", {"period": 30}, ("close",), lambda c: talib.SMA(c, timeperiod=30)),
    Pair("ema", {"period": 30}, ("close",), lambda c: talib.EMA(c, timeperiod=30)),
    Pair("wma", {"period": 30}, ("close",), lambda c: talib.WMA(c, timeperiod=30)),
    Pair("dema", {"period": 30}, ("close",), lambda c: talib.DEMA(c, timeperiod=30)),
    Pair("tema", {"period": 30}, ("close",), lambda c: talib.TEMA(c, timeperiod=30)),
    Pair("kama", {"period": 30}, ("close",), lambda c: talib.KAMA(c, timeperiod=30)),
    Pair(
        "macd",
        {"fast": 12, "slow": 26, "signal": 9},
        ("close",),
        lambda c: talib.MACD(c, fastperiod=12, slowperiod=26, signalperiod=9),
    ),
    Pair(
        "sar",
        {"acceleration": 0.02, "maximum": 0.2},
        ("high", "low"),
        lambda h, lo: talib.SAR(h, lo, acceleration=0.02, maximum=0.2),
    ),
    Pair("adx", {"period": 14}, HLC, _adx),
    Pair("aroon", {"period": 14}, ("high", "low"), _aroon),
    Pair("rsi", {"period": 14}, ("close",), lambda c: talib.RSI(c, timeperiod=14)),
    Pair("cci", {"period": 14}, HLC, lambda h, lo, c: talib.CCI(h, lo, c, timeperiod=14)),
    Pair(
        "stoch",
        {"k": 14, "k_smooth": 3, "d": 3},
        HLC,
        lambda h, lo, c: talib.STOCH(
            h,
            lo,
            c,
            fastk_period=14,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        ),
    ),
    Pair("willr", {"period": 14}, HLC, lambda h, lo, c: talib.WILLR(h, lo, c, timeperiod=14)),
    Pair("roc", {"period": 10}, ("close",), lambda c: talib.ROC(c, timeperiod=10)),
    Pair("mfi", {"period": 14}, HLCV, lambda h, lo, c, v: talib.MFI(h, lo, c, v, timeperiod=14)),
    Pair("trix", {"period": 30}, ("close",), lambda c: talib.TRIX(c, timeperiod=30)),
    Pair(
        "ultosc",
        {"short": 7, "medium": 14, "long": 28},
        HLC,
        lambda h, lo, c: talib.ULTOSC(h, lo, c, timeperiod1=7, timeperiod2=14, timeperiod3=28),
    ),
    Pair("atr", {"period": 14}, HLC, lambda h, lo, c: talib.ATR(h, lo, c, timeperiod=14)),
    Pair(
        "bbands",
        {"period": 20, "k": 2.0},
        ("close",),
        lambda c: talib.BBANDS(c, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0),
    ),
    Pair("stddev", {"period": 5, "k": 1.0}, ("close",), lambda c: talib.STDDEV(c, 5, nbdev=1.0)),
    Pair("obv", {}, ("close", "volume"), talib.OBV),
    Pair("ad", {}, HLCV, talib.AD),
)


def random_walk(rows: int, seed: int) -> Arrays:
    """Seeded OHLCV random walk: positive prices, high >= open/close >= low, positive volume."""
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, rows)))
    open_ = np.concatenate(([close[0]], close[:-1]))
    spread = np.abs(rng.normal(0.0, 0.005, rows)) * close
    return {
        "open": open_,
        "high": np.maximum(open_, close) + spread,
        "low": np.minimum(open_, close) - spread,
        "close": close,
        "volume": rng.integers(100_000, 5_000_000, rows).astype(np.float64),
    }


def yfinance_frame(arrays: Arrays) -> pd.DataFrame:
    """The arrays as yfinance returns them: title-case columns, Adj Close, a DatetimeIndex."""
    rows = len(arrays["close"])
    frame = pd.DataFrame({FRAME_COLUMNS[role]: arrays[role] for role in ROLES})
    frame.insert(4, "Adj Close", arrays["close"])
    frame.index = pd.date_range("1990-01-01", periods=rows, freq="min", name="Date")
    return frame


def talib_args(pair: Pair, data: Dataset) -> list[Any]:
    if isinstance(data, pd.DataFrame):
        return [data[FRAME_COLUMNS[role]] for role in pair.inputs]
    return [data[role] for role in pair.inputs]


def pyta_input(pair: Pair, data: Dataset) -> Dataset | np.ndarray:
    """A frame goes in whole; NumPy goes in as one array, or a dict of the named inputs."""
    if isinstance(data, pd.DataFrame):
        return data
    if len(pair.inputs) == 1:
        return data[pair.inputs[0]]
    return {role: data[role] for role in pair.inputs}


def outputs(result: Any) -> list[np.ndarray]:
    """Any single result (array, Series, tuple, dict, DataFrame) as float arrays in order."""
    if isinstance(result, pd.DataFrame):
        return [result[name].to_numpy(np.float64) for name in result.columns]
    if isinstance(result, dict):
        return [np.asarray(value, np.float64) for value in result.values()]
    if isinstance(result, tuple | list):
        return [np.asarray(value, np.float64) for value in result]
    return [np.asarray(result, np.float64)]


def largest_difference(pair: Pair, data: Dataset) -> float:
    """Largest relative difference between the libraries where both have a value."""
    ours = outputs(getattr(pyta, pair.name)(pyta_input(pair, data), **pair.params))
    theirs = outputs(pair.talib(*talib_args(pair, data)))
    assert len(ours) == len(theirs), f"{pair.name}: {len(ours)} outputs against {len(theirs)}"
    worst = 0.0
    for a, b in zip(ours, theirs, strict=True):
        both = ~np.isnan(a) & ~np.isnan(b)
        if both.any():
            scale = np.maximum(np.abs(b[both]), 1.0)
            worst = max(worst, float(np.max(np.abs(a[both] - b[both]) / scale)))
    return worst


def best_of(calls: Sequence[Callable[[], object]], repeat: int, target: float) -> list[float]:
    """Seconds per call for each callable, best of `repeat`, the callables alternating."""
    timers = [timeit.Timer(call) for call in calls]
    numbers = []
    for timer in timers:
        number, elapsed = timer.autorange()
        numbers.append(max(1, math.ceil(number * target / max(elapsed, 1e-9))))
    best = [math.inf] * len(timers)
    for _ in range(repeat):
        for i, (timer, number) in enumerate(zip(timers, numbers, strict=True)):
            best[i] = min(best[i], timer.timeit(number) / number)
    return best


@dataclass(frozen=True, slots=True)
class Row:
    indicator: str
    shape: str
    container: str
    talib_us: float
    pyta_us: float
    difference: float

    @property
    def ratio(self) -> float:
        return self.talib_us / self.pyta_us


def run_single(pair: Pair, rows: int, container: str, repeat: int, target: float) -> Row:
    arrays = random_walk(rows, seed=rows)
    data: Dataset = yfinance_frame(arrays) if container == "DataFrame" else arrays
    args = talib_args(pair, data)
    native = pyta_input(pair, data)
    function = getattr(pyta, pair.name)
    params = pair.params
    talib_s, pyta_s = best_of(
        [lambda: pair.talib(*args), lambda: function(native, **params)], repeat, target
    )
    return Row(
        pair.name,
        f"{rows:,}",
        container,
        talib_s * 1e6,
        pyta_s * 1e6,
        largest_difference(pair, data),
    )


def run_batch(
    pair: Pair, datasets: int, rows: int, container: str, repeat: int, target: float
) -> Row:
    walks = [random_walk(rows, seed=1_000 * datasets + i) for i in range(datasets)]
    data: list[Dataset] = (
        [yfinance_frame(walk) for walk in walks] if container == "DataFrame" else list(walks)
    )
    talib_inputs = [talib_args(pair, d) for d in data]
    pyta_inputs = [pyta_input(pair, d) for d in data]
    batch_function = getattr(pyta.batch, pair.name)
    params = pair.params
    results = batch_function(pyta_inputs, **params)
    failed = [r for r in results if isinstance(r, Exception)]
    assert not failed, f"{pair.name}: {failed[0]!r}"
    talib_s, pyta_s = best_of(
        [
            lambda: [pair.talib(*args) for args in talib_inputs],
            lambda: batch_function(pyta_inputs, **params),
        ],
        repeat,
        target,
    )
    return Row(
        pair.name,
        f"{datasets:,} x {rows:,}",
        container,
        talib_s * 1e6,
        pyta_s * 1e6,
        max(largest_difference(pair, d) for d in data[:3]),
    )


def table(rows: Sequence[Row], shape_header: str) -> list[str]:
    lines = [
        f"| Indicator | {shape_header} | Input | TA-Lib (µs) | PyTA (µs) "
        "| TA-Lib / PyTA | Largest difference |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {r.indicator} | {r.shape} | {r.container} | {r.talib_us:,.1f} | {r.pyta_us:,.1f} "
        f"| {r.ratio:.2f}x | {r.difference:.1e} |"
        for r in rows
    ]
    return lines


def governor() -> str:
    try:
        path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        return path.read_text().strip()
    except OSError:
        return "unknown"


def cpu_name() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def main(argv: Sequence[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true", help="3 repeats of ~0.02 s each")
    parser.add_argument("--repeat", type=int, default=5, help="repeats per case (best kept)")
    parser.add_argument("--indicator", nargs="+", help="only these PyTA names")
    parser.add_argument("--containers", nargs="+", default=["NumPy", "DataFrame"])
    args = parser.parse_args(argv)
    repeat, target = (3, 0.02) if args.quick else (args.repeat, 0.1)
    pairs = [p for p in PAIRS if not args.indicator or p.name in args.indicator]

    single: list[Row] = []
    batch: list[Row] = []
    for pair in pairs:
        for container in args.containers:
            for rows in SINGLE_ROWS:
                single.append(run_single(pair, rows, container, repeat, target))
                print(*table(single[-1:], "Rows")[2:], flush=True)
            for datasets, rows in BATCH_SHAPES:
                batch.append(run_batch(pair, datasets, rows, container, repeat, target))
                print(*table(batch[-1:], "Datasets x rows")[2:], flush=True)

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    header = [
        f"# PyTA {metadata.version('pyta')} against TA-Lib {talib.__version__}",
        "",
        f"- Date: {stamp}",
        f"- Machine: {cpu_name()}, {platform.system()} {platform.release()}, "
        f"governor `{governor()}`",
        f"- Python {platform.python_version()}, NumPy {np.__version__}, pandas {pd.__version__}",
        f"- Method: `timeit`, best of {repeat} repeats of ~{target} s, libraries alternating; "
        "the whole call is timed; seeded random-walk OHLCV.",
        "- TA-Lib / PyTA above 1 means PyTA is faster. Largest difference is relative "
        "(absolute below 1), where both have a value.",
        f"- No TA-Lib equivalent (not compared): {', '.join(NO_TALIB)}.",
        "",
        "## Single indicator (one dataset per call)",
        "",
        *table(single, "Rows"),
        "",
        "## Batch (TA-Lib: a loop of calls; PyTA: one `pyta.batch` call)",
        "",
        *table(batch, "Datasets x rows"),
        "",
    ]
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"compare_talib_{stamp}.md"
    path.write_text("\n".join(header))
    print(f"\nReport: {path}")
    return path


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
