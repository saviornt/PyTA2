"""Type stubs for the native extension module."""

import numpy as np
from numpy.typing import NDArray

def sma(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def rsi(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
