use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_batch;
use crate::single::compute;

/// Calculates the rolling population Standard Deviation (STDDEV) over
/// `period` values, multiplied by `k`.
///
/// Returns a float64 array with the same length as the input. Warm-up
/// positions are NaN.
#[pyfunction]
pub(crate) fn stddev<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
    k: f64,
) -> PyResult<Bound<'py, PyAny>> {
    compute(py, values, Params::Stddev { period, k })
}

/// Calculates the STDDEV of many datasets at once.
///
/// Returns a list in input order. Each entry is a float64 array, or the
/// exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn stddev_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
    k: f64,
) -> PyResult<Bound<'py, PyList>> {
    compute_batch(py, datasets, Params::Stddev { period, k })
}
