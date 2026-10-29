use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates Keltner Channels from high, low and close: the EMA of close
/// over `period`, with bands `k` ATRs (over `atr_period`) above and below it.
///
/// `columns` are the high, low and close arrays, in that order. Returns a
/// list of three float64 arrays (upper, middle, lower), each the same length
/// as the input. Warm-up positions are NaN: the middle line's first
/// `period - 1`, the bands' first `max(period - 1, atr_period)`.
#[pyfunction]
pub(crate) fn keltner<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    period: usize,
    atr_period: usize,
    k: f64,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(
        py,
        columns,
        Params::Keltner {
            period,
            atr_period,
            k,
        },
    )
}

/// Calculates the Keltner Channels of many datasets at once.
///
/// Each dataset is a list of its high, low and close arrays. Returns a list
/// in input order. Each entry is a list of three float64 arrays (upper,
/// middle, lower), or the exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn keltner_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
    atr_period: usize,
    k: f64,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(
        py,
        datasets,
        Params::Keltner {
            period,
            atr_period,
            k,
        },
    )
}
