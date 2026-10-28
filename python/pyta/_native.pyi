"""Type stubs for the native extension module."""

import numpy as np
from numpy.typing import NDArray

MAX_ABS_INPUT: float

def sma(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def rsi(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def sma_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def rsi_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
