use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_batch;
use crate::single::compute;

/// Calculates the Exponential Moving Average (EMA), seeded with the simple
/// average of the first `period` values as TA-Lib does.
///
/// Returns a float64 array with the same length as the input. Warm-up
/// positions are NaN.
#[pyfunction]
pub(crate) fn ema<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute(py, values, Params::Ema { period })
}

/// Calculates the EMA of many datasets at once.
///
/// Returns a list in input order. Each entry is a float64 array, or the
/// exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn ema_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_batch(py, datasets, Params::Ema { period })
}
