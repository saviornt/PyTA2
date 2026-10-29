"""Logging: Rust and Python messages in one stream, and silence by default."""

import logging
import subprocess
import sys

import numpy as np
import pyta
import pytest

PYTA_LOGGERS = ["pyta.api", "pyta.validation", "pyta.engine", "pyta.planner", "pyta.bridge"]


def _large_batch() -> list[np.ndarray]:
    """Large enough that the planner chooses the parallel path."""
    return [np.linspace(1.0, 2.0, 10_000) for _ in range(16)]


def messages(caplog: pytest.LogCaptureFixture, logger: str) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == logger]


def test_rust_planner_logs_its_choice_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="pyta")

    pyta.batch.sma([[1.0] * 50] * 20, period=5)
    pyta.batch.sma(_large_batch(), period=5)

    small, large = messages(caplog, "pyta.planner")
    assert small.startswith("20 requests on ")
    assert small.endswith(": sequential")
    assert "ns sequential" in large
    assert large.endswith(": parallel")


def test_rust_records_carry_level_and_source(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="pyta")

    pyta.batch.rsi([[1.0] * 50] * 2, period=5)

    (record,) = [r for r in caplog.records if r.name == "pyta.planner"]
    assert record.levelno == logging.DEBUG
    assert record.filename == "planner.rs"
    assert record.lineno > 0


def test_python_batch_failures_log_each_at_debug_and_a_warning_summary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="pyta")
    datasets = {"good": [1.0, 2.0, 3.0], "short": [1.0], "text": ["a", "b"]}

    pyta.batch.sma(datasets, period=2)

    api = [(r.levelno, r.getMessage()) for r in caplog.records if r.name == "pyta.api"]
    assert api == [
        (
            logging.DEBUG,
            "sma: dataset 'short' failed: period (2) exceeds the series length (1); "
            "use a smaller period or provide more data",
        ),
        (
            logging.DEBUG,
            "sma: dataset 'text' failed: input value 'a' at index 0 is not a number; "
            "expected a number, an empty field or NaN",
        ),
        (logging.WARNING, "sma: 2 of 3 datasets failed; each failure is returned in its place"),
    ]


def test_successful_batch_logs_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="pyta")

    pyta.batch.sma([[1.0, 2.0, 3.0]], period=2)

    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_column_resolution_logs_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="pyta")

    pyta.sma({"Open": [1.0, 2.0], "Adj Close": [3.0, 4.0]}, period=1, column="adjusted close")

    assert messages(caplog, "pyta.validation") == ["using column 'Adj Close' for 'adjusted close'"]


def test_debug_is_off_at_the_default_level(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)

    pyta.batch.sma([[1.0] * 50] * 20 + [[1.0]], period=5)

    assert [r.name for r in caplog.records] == ["pyta.api"]
    assert caplog.records[0].levelno == logging.WARNING


def test_rust_picks_up_a_level_changed_after_earlier_calls(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="pyta")
    pyta.batch.sma([[1.0] * 50] * 2, period=5)
    assert not messages(caplog, "pyta.planner")

    caplog.set_level(logging.DEBUG, logger="pyta.planner")
    pyta.batch.sma([[1.0] * 50] * 2, period=5)

    assert len(messages(caplog, "pyta.planner")) == 1


def test_single_calls_log_nothing_from_rust(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="pyta")

    pyta.sma(np.ones(1_000), period=5)
    pyta.rsi(np.ones(1_000), period=5)

    assert not [
        r for r in caplog.records if r.name in ("pyta.engine", "pyta.planner", "pyta.bridge")
    ]


def test_library_adds_only_a_null_handler() -> None:
    (handler,) = logging.getLogger("pyta").handlers

    assert type(handler) is logging.NullHandler
    assert logging.getLogger("pyta").level == logging.NOTSET
    for name in PYTA_LOGGERS:
        assert logging.getLogger(name).handlers == []
        assert logging.getLogger(name).level == logging.NOTSET


def test_unconfigured_library_is_silent() -> None:
    code = (
        "import logging, pyta\n"
        "pyta.batch.sma([[1.0], [1.0, 2.0, 3.0]], period=2)\n"
        "print(logging.getLogger().handlers)\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stderr == ""
    assert result.stdout.strip() == "[]"


def test_one_stream_with_basic_config() -> None:
    """The documented setup: Rust and Python messages arrive through one handler."""
    code = (
        "import logging, pyta\n"
        "logging.basicConfig(level='DEBUG', format='%(name)s %(message)s')\n"
        "pyta.batch.sma([[1.0] * 50] * 20 + [[1.0]], period=5)\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    names = [line.split()[0] for line in result.stderr.splitlines()]

    assert names == ["pyta.planner", "pyta.api", "pyta.api"]
