"""Batch calls after `fork()`.

The native engine runs large batches on a Rayon thread pool, and a forked
child does not inherit its worker threads. These tests show whether a child
process can still run batches, which matters for users of `multiprocessing`
with the `fork` start method.
"""

import logging
import multiprocessing
import sys

import numpy as np
import pyta
import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="fork is not available on Windows")


def _large_batch() -> list[np.ndarray]:
    """Large enough that the planner chooses the parallel path."""
    rng = np.random.default_rng(0)
    return [rng.uniform(1.0, 2.0, 10_000) for _ in range(64)]


def _child(queue: multiprocessing.Queue[bool]) -> None:
    results = pyta.batch.sma(_large_batch(), period=5)
    queue.put(all(isinstance(r, np.ndarray) for r in results))


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.parametrize("warm_parent", [False, True])
def test_forked_child_can_run_a_parallel_batch(warm_parent):
    if warm_parent:
        # Starts the Rayon pool in the parent before forking.
        pyta.batch.sma(_large_batch(), period=5)

    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    child = context.Process(target=_child, args=(queue,))
    child.start()
    child.join(timeout=30)

    if child.is_alive():
        child.kill()
        child.join()
        pytest.fail("forked child hung running a parallel batch")

    assert child.exitcode == 0
    assert queue.get(timeout=5) is True


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append((record.name, record.getMessage()))


def _logging_child(queue: multiprocessing.Queue[list[tuple[str, str]]]) -> None:
    handler = _ListHandler()
    logger = logging.getLogger("pyta")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    pyta.batch.sma(_large_batch(), period=5)
    queue.put(handler.records)


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_forked_child_logs_the_pool_rebuild() -> None:
    # Starts the Rayon pool in the parent, so the child must rebuild it.
    pyta.batch.sma(_large_batch(), period=5)

    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    child = context.Process(target=_logging_child, args=(queue,))
    child.start()
    records = queue.get(timeout=30)
    child.join(timeout=30)

    assert child.exitcode == 0
    names = [name for name, _ in records]
    assert names == ["pyta.planner", "pyta.bridge", "pyta.bridge"]
    assert records[0][1].endswith(": parallel")
    assert records[1][1].startswith("rebuilding the worker pool after fork")
    assert records[2][1].startswith("started the worker pool with ")
