"""Type stubs for the native extension module."""

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "MAX_ABS_INPUT",
    "ad",
    "ad_batch",
    "adx",
    "adx_batch",
    "aroon",
    "aroon_batch",
    "atr",
    "atr_batch",
    "bbands",
    "bbands_batch",
    "cci",
    "cci_batch",
    "dema",
    "dema_batch",
    "donchian",
    "donchian_batch",
    "ema",
    "ema_batch",
    "ichimoku",
    "ichimoku_batch",
    "kama",
    "kama_batch",
    "keltner",
    "keltner_batch",
    "macd",
    "macd_batch",
    "mfi",
    "mfi_batch",
    "obv",
    "obv_batch",
    "roc",
    "roc_batch",
    "rsi",
    "rsi_batch",
    "sar",
    "sar_batch",
    "sma",
    "sma_batch",
    "stddev",
    "stddev_batch",
    "stoch",
    "stoch_batch",
    "tema",
    "tema_batch",
    "trix",
    "trix_batch",
    "ultosc",
    "ultosc_batch",
    "willr",
    "willr_batch",
    "wma",
    "wma_batch",
]

MAX_ABS_INPUT: float

def sma(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def rsi(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def ema(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def wma(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def dema(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def tema(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def kama(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def roc(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def roc_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def trix(values: NDArray[np.float64], period: int) -> NDArray[np.float64]: ...
def trix_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def sma_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def rsi_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def ema_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def dema_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def tema_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def kama_batch(
    datasets: list[NDArray[np.float64]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def wma_batch(
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
def stoch(
    columns: list[NDArray[np.float64]], k: int, k_smooth: int, d: int
) -> list[NDArray[np.float64]]: ...
def stoch_batch(
    datasets: list[list[NDArray[np.float64]]], k: int, k_smooth: int, d: int
) -> list[list[NDArray[np.float64]] | Exception]: ...
def willr(columns: list[NDArray[np.float64]], period: int) -> NDArray[np.float64]: ...
def willr_batch(
    datasets: list[list[NDArray[np.float64]]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def ultosc(
    columns: list[NDArray[np.float64]], short: int, medium: int, long: int
) -> NDArray[np.float64]: ...
def ultosc_batch(
    datasets: list[list[NDArray[np.float64]]], short: int, medium: int, long: int
) -> list[NDArray[np.float64] | Exception]: ...
def mfi(columns: list[NDArray[np.float64]], period: int) -> NDArray[np.float64]: ...
def mfi_batch(
    datasets: list[list[NDArray[np.float64]]], period: int
) -> list[NDArray[np.float64] | Exception]: ...
def adx(columns: list[NDArray[np.float64]], period: int) -> list[NDArray[np.float64]]: ...
def adx_batch(
    datasets: list[list[NDArray[np.float64]]], period: int
) -> list[list[NDArray[np.float64]] | Exception]: ...
def aroon(columns: list[NDArray[np.float64]], period: int) -> list[NDArray[np.float64]]: ...
def aroon_batch(
    datasets: list[list[NDArray[np.float64]]], period: int
) -> list[list[NDArray[np.float64]] | Exception]: ...
def ichimoku(
    columns: list[NDArray[np.float64]], tenkan: int, kijun: int, senkou: int
) -> list[NDArray[np.float64]]: ...
def ichimoku_batch(
    datasets: list[list[NDArray[np.float64]]], tenkan: int, kijun: int, senkou: int
) -> list[list[NDArray[np.float64]] | Exception]: ...
def sar(
    columns: list[NDArray[np.float64]], acceleration: float, maximum: float
) -> NDArray[np.float64]: ...
def sar_batch(
    datasets: list[list[NDArray[np.float64]]], acceleration: float, maximum: float
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
def donchian(columns: list[NDArray[np.float64]], period: int) -> list[NDArray[np.float64]]: ...
def donchian_batch(
    datasets: list[list[NDArray[np.float64]]], period: int
) -> list[list[NDArray[np.float64]] | Exception]: ...
def obv(columns: list[NDArray[np.float64]]) -> NDArray[np.float64]: ...
def ad(columns: list[NDArray[np.float64]]) -> NDArray[np.float64]: ...
def ad_batch(
    datasets: list[list[NDArray[np.float64]]],
) -> list[NDArray[np.float64] | Exception]: ...
def obv_batch(
    datasets: list[list[NDArray[np.float64]]],
) -> list[NDArray[np.float64] | Exception]: ...
def keltner(
    columns: list[NDArray[np.float64]], period: int, atr_period: int, k: float
) -> list[NDArray[np.float64]]: ...
def keltner_batch(
    datasets: list[list[NDArray[np.float64]]], period: int, atr_period: int, k: float
) -> list[list[NDArray[np.float64]] | Exception]: ...
