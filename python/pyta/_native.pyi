"""Type stubs for the native extension module."""

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "MAX_ABS_INPUT",
    "atr",
    "atr_batch",
    "bbands",
    "bbands_batch",
    "cci",
    "cci_batch",
    "ema",
    "ema_batch",
    "macd",
    "macd_batch",
    "rsi",
    "rsi_batch",
    "sma",
    "sma_batch",
    "stddev",
    "stddev_batch",
]

MAX_ABS_INPUT: float

def sma(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def rsi(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def ema(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def sma_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def rsi_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def ema_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def atr(columns: list[NDArray[np.float64]], period: int) -> NDArray[np.float64]: ...
def atr_batch(
    datasets: list[list[NDArray[np.float64]]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def cci(columns: list[NDArray[np.float64]], period: int) -> NDArray[np.float64]: ...
def cci_batch(
    datasets: list[list[NDArray[np.float64]]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def macd(
    values: NDArray[np.float64], fast: int, slow: int, signal: int
) -> list[NDArray[np.float64]]: ...
def macd_batch(
    datasets: list[NDArray[np.float64]], fast: int, slow: int, signal: int
) -> list[list[NDArray[np.float64]] | Exception]: ...
def stddev(values: NDArray[np.float64], period: int, k: float) -> NDArray[np.float64]: ...
def stddev_batch(
    datasets: list[NDArray[np.float64]], period: int, k: float
) -> list[NDArray[np.float64] | Exception]: ...
def bbands(values: NDArray[np.float64], period: int, k: float) -> list[NDArray[np.float64]]: ...
def bbands_batch(
    datasets: list[NDArray[np.float64]], period: int, k: float
) -> list[list[NDArray[np.float64]] | Exception]: ...
