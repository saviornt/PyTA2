use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_batch;
use crate::single::compute;

/// Calculates Bollinger Bands (BBANDS): the `period` simple moving average
/// with bands `k` population standard deviations above and below it.
///
/// Returns a list of three float64 arrays (upper, middle, lower), each the
/// same length as the input. Warm-up positions are NaN.
#[pyfunction]
pub(crate) fn bbands<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
    k: f64,
) -> PyResult<Bound<'py, PyAny>> {
    compute(py, values, Params::Bbands { period, k })
}

/// Calculates the Bollinger Bands of many datasets at once.
///
/// Returns a list in input order. Each entry is a list of three float64
/// arrays (upper, middle, lower), or the exception explaining why that
/// dataset failed.
#[pyfunction]
pub(crate) fn bbands_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
    k: f64,
) -> PyResult<Bound<'py, PyList>> {
    compute_batch(py, datasets, Params::Bbands { period, k })
}
