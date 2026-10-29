use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates the Ichimoku Cloud from high, low and close, unshifted: the
/// midpoints of the highest high and lowest low over `tenkan`, `kijun` and
/// `senkou` rows, the average of the first two, and close.
///
/// `columns` are the high, low and close arrays, in that order. Returns a
/// list of five float64 arrays (tenkan-sen, kijun-sen, senkou span A,
/// senkou span B, chikou span), each the same length as the input and on the
/// row it is calculated from. Warm-up positions are NaN: the first
/// `tenkan - 1`, `kijun - 1`, `max(tenkan, kijun) - 1` and `senkou - 1` of
/// the first four; the chikou span has none.
#[pyfunction]
pub(crate) fn ichimoku<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    tenkan: usize,
    kijun: usize,
    senkou: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(
        py,
        columns,
        Params::Ichimoku {
            tenkan,
            kijun,
            senkou,
        },
    )
}

/// Calculates the Ichimoku Cloud of many datasets at once.
///
/// Each dataset is a list of its high, low and close arrays. Returns a list
/// in input order. Each entry is a list of five float64 arrays (tenkan-sen,
/// kijun-sen, senkou span A, senkou span B, chikou span), or the exception
/// explaining why that dataset failed.
#[pyfunction]
pub(crate) fn ichimoku_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    tenkan: usize,
    kijun: usize,
    senkou: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(
        py,
        datasets,
        Params::Ichimoku {
            tenkan,
            kijun,
            senkou,
        },
    )
}
