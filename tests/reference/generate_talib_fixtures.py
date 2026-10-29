"""Writes the Sprint 11.5 TA-Lib reference fixtures in `tests/fixtures/`.

TA-Lib is never a PyTA dependency: run this with a throwaway environment that
has it, never the project's `.venv` (pytest does not collect it: no `test_`
prefix, and nothing imports it):

    uv venv --python 3.15 <scratch>/talib-env
    VIRTUAL_ENV=<scratch>/talib-env uv pip install TA-Lib==0.8.3 numpy
    <scratch>/talib-env/bin/python -I tests/reference/generate_talib_fixtures.py

It reads the SPY sessions in `ohlcv_daily.csv`, writes the synthetic edge-case
input `edge_ohlcv.csv`, and writes one fixture per indicator and parameter set
for each input (`<name>_<params>_talib.csv` on SPY, `<name>_<params>_edge_talib.csv`
on the edge series), in the format `reference_data.py` reads. Values are
TA-Lib's own doubles printed with `repr`; warm-up (NaN) is an empty field.
"""

import csv
import math
import platform
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import talib  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]

# TA-Lib ships no type information.
ta: Any = talib

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TOLERANCE = "1e-9"
ROLES = ("open", "high", "low", "close", "volume")

type Columns = dict[str, np.ndarray[Any, np.dtype[np.float64]]]
type Outputs = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Dataset:
    """One input table: row labels, the values as written, and float64 columns."""

    tag: str  # "" for SPY, "_edge" for the edge series
    description: str
    labels: list[str]
    text: dict[str, list[str]]
    columns: Columns


@dataclass(frozen=True, slots=True)
class Fixture:
    """One indicator and parameter set."""

    stem: str
    title: str
    call: str
    inputs: Sequence[str]  # roles in slot order; a single one is written as `input`
    parameters: Sequence[tuple[str, str]]
    compute: Callable[[Columns], Outputs]
    notes: Sequence[str] = ()


def _source() -> str:
    c_version = ta.__ta_version__
    if isinstance(c_version, bytes):
        c_version = c_version.decode()
    c_release = str(c_version).split()[0]
    python = ".".join(platform.python_version_tuple()[:2])
    return (
        f"generated with TA-Lib {ta.__version__} (PyPI wheel, bundled C library {c_release}), "
        f"Python {python}, NumPy {np.__version__} in a throwaway environment "
        "(TA-Lib is not a dependency)"
    )


def _read_spy() -> Dataset:
    lines = [
        line
        for line in (FIXTURES / "ohlcv_daily.csv").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    rows = list(csv.DictReader(lines))
    text = {role: [row[role] for row in rows] for role in ROLES}
    return Dataset(
        tag="",
        description="tests/fixtures/ohlcv_daily.csv (300 SPY sessions, 2024-10-21 to 2025-12-31)",
        labels=[row["date"] for row in rows],
        text=text,
        columns={role: np.array([float(v) for v in values]) for role, values in text.items()},
    )


EDGE_ROWS = 120
FLAT = range(40, 76)  # 36 rows with open == high == low == close
FLAT_PRICE = 105.0
ZERO_VOLUME = (*range(50, 66), 85, 86)  # 16 rows inside the flat stretch, 2 outside
HIGH_EQUALS_LOW = 80  # a one-price bar off the flat level
ZERO_BAR = 95  # open == high == low == close == 0, so ROC 10 has a zero base at row 105


def _edge_rows() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    previous = 99.5
    for i in range(EDGE_ROWS):
        if i in FLAT:
            o = h = l = c = FLAT_PRICE  # noqa: E741
        elif i == ZERO_BAR:
            o = h = l = c = 0.0  # noqa: E741
        else:
            c = round(100 + 4 * math.sin(i * 0.45) + 0.15 * i, 2)
            o = previous if previous > 0 else c
            if i == HIGH_EQUALS_LOW:
                o = h = l = c  # noqa: E741
            else:
                h = round(max(o, c) + 0.3 + 0.05 * ((i * 7) % 5), 2)
                l = round(min(o, c) - 0.25 - 0.05 * ((i * 3) % 5), 2)  # noqa: E741
        volume = 0.0 if i in ZERO_VOLUME else float(300_000 + (i * 7919) % 500_000)
        rows.append({"open": o, "high": h, "low": l, "close": c, "volume": volume})
        previous = c
    return rows


def _edge_text(role: str, value: float) -> str:
    return str(int(value)) if role == "volume" else f"{value:.2f}"


def _write_edge(retrieved: str) -> Dataset:
    rows = _edge_rows()
    text = {role: [_edge_text(role, row[role]) for row in rows] for role in ROLES}
    header = [
        f"# Synthetic OHLCV edge cases for the TA-Lib fixtures: {EDGE_ROWS} rows, "
        "labelled by row number.",
        "# source: written by tests/reference/generate_talib_fixtures.py "
        "(deterministic formula, no randomness)",
        f"# retrieved: {retrieved}",
        "# Rows 0-39 and 76-119 move (close = 100 + 4 sin(0.45 i) + 0.15 i, "
        "open = previous close);",
        f"# rows {FLAT.start}-{FLAT.stop - 1} are flat "
        f"(open == high == low == close == {FLAT_PRICE:.2f}, "
        "36 rows, longer than any default window, to hit flat-window guards);",
        f"# volume is 0 on rows {ZERO_VOLUME[0]}-{ZERO_VOLUME[15]} (inside the flat stretch) "
        f"and {ZERO_VOLUME[16]}, {ZERO_VOLUME[17]};",
        f"# row {HIGH_EQUALS_LOW} is a one-price bar (high == low) off the flat level;",
        f"# row {ZERO_BAR} is a zero bar (open == high == low == close == 0), "
        "so ROC 10 has a zero base "
        f"at row {ZERO_BAR + 10}.",
    ]
    body = ["row," + ",".join(ROLES)]
    body += [f"{i}," + ",".join(text[role][i] for role in ROLES) for i in range(EDGE_ROWS)]
    (FIXTURES / "edge_ohlcv.csv").write_text("\n".join(header + body) + "\n")
    return Dataset(
        tag="_edge",
        description=f"tests/fixtures/edge_ohlcv.csv ({EDGE_ROWS} synthetic edge-case rows)",
        labels=[str(i) for i in range(EDGE_ROWS)],
        text=text,
        columns={role: np.array([row[role] for row in rows]) for role in ROLES},
    )


def _value(x: float) -> str:
    return "" if math.isnan(x) else repr(float(x))


def _write(fixture: Fixture, data: Dataset, source: str, retrieved: str) -> str:
    outputs = fixture.compute(data.columns)
    single = len(fixture.inputs) == 1
    role_names = ", ".join(fixture.inputs)
    input_line = (
        f"# input: the {fixture.inputs[0]} column of {data.description}"
        if single
        else f"# input: the {role_names} columns of {data.description}"
    )
    lines = [
        f"# {fixture.title}: {fixture.call}",
        f"# source: {source}",
        input_line,
        f"# retrieved: {retrieved}",
        *(f"# {note}" for note in fixture.notes),
        *(f"# {key}: {value}" for key, value in fixture.parameters),
        "# Values are TA-Lib's own doubles printed with repr; compared to 1e-9.",
        f"# tolerance: {TOLERANCE}",
        "# Empty expected values are the warm-up (NaN).",
    ]
    in_names = ["input"] if single else list(fixture.inputs)
    out_names = ["expected"] if len(outputs) == 1 else [f"expected_{name}" for name in outputs]
    lines.append(",".join(["label", *in_names, *out_names]))
    arrays = [np.asarray(values, dtype=np.float64) for values in outputs.values()]
    for i, label in enumerate(data.labels):
        cells = [label, *(data.text[role][i] for role in fixture.inputs)]
        cells += [_value(float(array[i])) for array in arrays]
        lines.append(",".join(cells))
    name = fixture.stem.replace("{tag}", data.tag)
    (FIXTURES / name).write_text("\n".join(lines) + "\n")
    first = {key: _first_valid(np.asarray(v, dtype=np.float64)) for key, v in outputs.items()}
    return f"{name}: first valid row {first}"


def _first_valid(values: np.ndarray[Any, np.dtype[np.float64]]) -> int | None:
    valid = np.flatnonzero(~np.isnan(values))
    return int(valid[0]) if valid.size else None


STOCH_NOTE = (
    "The expected_stoch_k column comes from talib.STOCH(..., slowd_period=1), identical where both "
    "have values: TA-Lib blanks",
    "slowk until slowd exists (row k + k_smooth + d - 3), while PyTA keeps each output's own "
    "warm-up (stoch_k from row k + k_smooth - 2).",
)


def _stoch(k: int, k_smooth: int, d: int) -> Callable[[Columns], Outputs]:
    def compute(c: Columns) -> Outputs:
        hlc = (c["high"], c["low"], c["close"])
        slow_k, _ = ta.STOCH(
            *hlc, fastk_period=k, slowk_period=k_smooth, slowk_matype=0, slowd_period=1
        )
        common_k, slow_d = ta.STOCH(
            *hlc, fastk_period=k, slowk_period=k_smooth, slowk_matype=0, slowd_period=d,
            slowd_matype=0,
        )  # fmt: skip
        both = ~np.isnan(common_k)
        assert np.array_equal(slow_k[both], common_k[both]), "slowk depends on slowd_period"
        return {"stoch_k": slow_k, "stoch_d": slow_d}

    return compute


def _fixtures() -> list[Fixture]:
    hlc = ("high", "low", "close")
    hlcv = ("high", "low", "close", "volume")
    fixtures = [
        *(
            Fixture(
                stem=f"wma_{p}{{tag}}_talib.csv",
                title=f"WMA, period {p}",
                call=f"talib.WMA(close, timeperiod={p})",
                inputs=("close",),
                parameters=(("period", str(p)),),
                compute=lambda c, p=p: {"wma": ta.WMA(c["close"], timeperiod=p)},
            )
            for p in (30, 10)
        ),
        Fixture(
            stem="dema_30{tag}_talib.csv",
            title="DEMA, period 30",
            call="talib.DEMA(close, timeperiod=30)",
            inputs=("close",),
            parameters=(("period", "30"),),
            compute=lambda c: {"dema": ta.DEMA(c["close"], timeperiod=30)},
        ),
        Fixture(
            stem="tema_30{tag}_talib.csv",
            title="TEMA, period 30",
            call="talib.TEMA(close, timeperiod=30)",
            inputs=("close",),
            parameters=(("period", "30"),),
            compute=lambda c: {"tema": ta.TEMA(c["close"], timeperiod=30)},
        ),
        Fixture(
            stem="kama_30{tag}_talib.csv",
            title="KAMA, period 30",
            call=(
                "talib.KAMA(close, timeperiod=30) "
                "(fast 2, slow 30 smoothing constants, fixed in TA-Lib)"
            ),
            inputs=("close",),
            parameters=(("period", "30"),),
            compute=lambda c: {"kama": ta.KAMA(c["close"], timeperiod=30)},
        ),
        Fixture(
            stem="adx_14{tag}_talib.csv",
            title="ADX, period 14",
            call="talib.ADX, talib.PLUS_DI and talib.MINUS_DI(high, low, close, timeperiod=14)",
            inputs=hlc,
            parameters=(("period", "14"),),
            compute=lambda c: {
                "adx": ta.ADX(c["high"], c["low"], c["close"], timeperiod=14),
                "adx_plus_di": ta.PLUS_DI(c["high"], c["low"], c["close"], timeperiod=14),
                "adx_minus_di": ta.MINUS_DI(c["high"], c["low"], c["close"], timeperiod=14),
            },
            notes=("Each output is its own TA-Lib call, so each keeps its own warm-up.",),
        ),
        *(
            Fixture(
                stem=f"sar_{a}_{m}{{tag}}_talib.csv",
                title=f"Parabolic SAR, acceleration {a}, maximum {m}",
                call=f"talib.SAR(high, low, acceleration={a}, maximum={m})",
                inputs=("high", "low"),
                parameters=(("acceleration", str(a)), ("maximum", str(m))),
                compute=lambda c, a=a, m=m: {
                    "sar": ta.SAR(c["high"], c["low"], acceleration=a, maximum=m)
                },
            )
            for a, m in ((0.02, 0.2), (0.01, 0.1))
        ),
        Fixture(
            stem="aroon_14{tag}_talib.csv",
            title="Aroon, period 14",
            call=(
                "talib.AROON(high, low, timeperiod=14) and talib.AROONOSC(high, low, timeperiod=14)"
            ),
            inputs=("high", "low"),
            parameters=(("period", "14"),),
            compute=_aroon,
            notes=("TA-Lib returns (aroondown, aroonup); the columns are in PyTA's order below.",),
        ),
        *(
            Fixture(
                stem=f"stoch_{k}_{ks}_{d}{{tag}}_talib.csv",
                title=f"Stochastic, k {k}, k_smooth {ks}, d {d}",
                call=(
                    f"talib.STOCH(high, low, close, fastk_period={k}, slowk_period={ks}, "
                    f"slowk_matype=0, slowd_period={d}, slowd_matype=0)"
                ),
                inputs=hlc,
                parameters=(("k", str(k)), ("k_smooth", str(ks)), ("d", str(d))),
                compute=_stoch(k, ks, d),
                notes=STOCH_NOTE,
            )
            for k, ks, d in ((14, 3, 3), (5, 3, 3))
        ),
        Fixture(
            stem="willr_14{tag}_talib.csv",
            title="Williams %R, period 14",
            call="talib.WILLR(high, low, close, timeperiod=14)",
            inputs=hlc,
            parameters=(("period", "14"),),
            compute=lambda c: {"willr": ta.WILLR(c["high"], c["low"], c["close"], timeperiod=14)},
        ),
        Fixture(
            stem="roc_10{tag}_talib.csv",
            title="ROC, period 10",
            call="talib.ROC(close, timeperiod=10)",
            inputs=("close",),
            parameters=(("period", "10"),),
            compute=lambda c: {"roc": ta.ROC(c["close"], timeperiod=10)},
        ),
        Fixture(
            stem="mfi_14{tag}_talib.csv",
            title="MFI, period 14",
            call="talib.MFI(high, low, close, volume, timeperiod=14)",
            inputs=hlcv,
            parameters=(("period", "14"),),
            compute=lambda c: {
                "mfi": ta.MFI(c["high"], c["low"], c["close"], c["volume"], timeperiod=14)
            },
        ),
        *(
            Fixture(
                stem=f"trix_{p}{{tag}}_talib.csv",
                title=f"TRIX, period {p}",
                call=f"talib.TRIX(close, timeperiod={p})",
                inputs=("close",),
                parameters=(("period", str(p)),),
                compute=lambda c, p=p: {"trix": ta.TRIX(c["close"], timeperiod=p)},
            )
            for p in (30, 15)
        ),
        Fixture(
            stem="ultosc_7_14_28{tag}_talib.csv",
            title="Ultimate Oscillator, short 7, medium 14, long 28",
            call="talib.ULTOSC(high, low, close, timeperiod1=7, timeperiod2=14, timeperiod3=28)",
            inputs=hlc,
            parameters=(("short", "7"), ("medium", "14"), ("long", "28")),
            compute=lambda c: {
                "ultosc": ta.ULTOSC(
                    c["high"], c["low"], c["close"], timeperiod1=7, timeperiod2=14, timeperiod3=28
                )
            },
        ),
        Fixture(
            stem="atr_14{tag}_talib.csv",
            title="ATR, period 14",
            call="talib.ATR(high, low, close, timeperiod=14)",
            inputs=hlc,
            parameters=(("period", "14"),),
            compute=lambda c: {"atr": ta.ATR(c["high"], c["low"], c["close"], timeperiod=14)},
        ),
        Fixture(
            stem="bbands_20_2{tag}_talib.csv",
            title="Bollinger Bands, period 20, k 2.0",
            call="talib.BBANDS(close, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)",
            inputs=("close",),
            parameters=(("period", "20"), ("k", "2.0")),
            compute=lambda c: dict(
                zip(
                    ("bbands_upper", "bbands_middle", "bbands_lower"),
                    ta.BBANDS(c["close"], timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0),
                    strict=True,
                )
            ),
        ),
        *(
            Fixture(
                stem=f"stddev_{p}_{int(k)}{{tag}}_talib.csv",
                title=f"Standard deviation, period {p}, k {k}",
                call=f"talib.STDDEV(close, timeperiod={p}, nbdev={k}) (population)",
                inputs=("close",),
                parameters=(("period", str(p)), ("k", str(k))),
                compute=lambda c, p=p, k=k: {
                    "stddev": ta.STDDEV(c["close"], timeperiod=p, nbdev=k)
                },
            )
            for p, k in ((5, 1.0), (20, 2.0))
        ),
        Fixture(
            stem="donchian_20{tag}_talib.csv",
            title="Donchian Channels, period 20",
            call="talib.MAX(high, timeperiod=20) and talib.MIN(low, timeperiod=20)",
            inputs=("high", "low"),
            parameters=(("period", "20"),),
            compute=lambda c: _donchian(
                ta.MAX(c["high"], timeperiod=20), ta.MIN(c["low"], timeperiod=20)
            ),
            notes=(
                "Donchian Channels are not a TA-Lib function: upper is MAX(high), "
                "lower is MIN(low), both including the current row,",
                "and middle is (upper + lower) / 2 computed here in float64.",
            ),
        ),
        Fixture(
            stem="obv{tag}_talib.csv",
            title="OBV",
            call="talib.OBV(close, volume)",
            inputs=("close", "volume"),
            parameters=(),
            compute=lambda c: {"obv": ta.OBV(c["close"], c["volume"])},
        ),
        Fixture(
            stem="ad{tag}_talib.csv",
            title="Accumulation/Distribution",
            call="talib.AD(high, low, close, volume)",
            inputs=hlcv,
            parameters=(),
            compute=lambda c: {"ad": ta.AD(c["high"], c["low"], c["close"], c["volume"])},
        ),
        Fixture(
            stem="vroc_10{tag}_talib.csv",
            title="Volume ROC, period 10",
            call="talib.ROC(volume, timeperiod=10)",
            inputs=("volume",),
            parameters=(("period", "10"),),
            compute=lambda c: {"vroc": ta.ROC(c["volume"], timeperiod=10)},
        ),
    ]
    return fixtures


def _aroon(c: Columns) -> Outputs:
    down, up = ta.AROON(c["high"], c["low"], timeperiod=14)
    return {
        "aroon_up": up,
        "aroon_down": down,
        "aroon_osc": ta.AROONOSC(c["high"], c["low"], timeperiod=14),
    }


def _donchian(upper: Any, lower: Any) -> Outputs:
    return {
        "donchian_upper": upper,
        "donchian_middle": (upper + lower) / 2,
        "donchian_lower": lower,
    }


def main() -> None:
    retrieved = date.today().isoformat()
    source = _source()
    spy = _read_spy()
    edge = _write_edge(retrieved)
    for fixture in _fixtures():
        print(_write(fixture, spy, source, retrieved))
    # The edge series gets the default parameter sets only.
    extra = ("wma_10", "sar_0.01", "stoch_5", "trix_15", "stddev_20")
    for fixture in _fixtures():
        if not fixture.stem.startswith(extra):
            print(_write(fixture, edge, source, retrieved))


if __name__ == "__main__":
    main()
