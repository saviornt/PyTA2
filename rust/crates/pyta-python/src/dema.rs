use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_batch;
use crate::single::compute;

/// Calculates the Double Exponential Moving Average (DEMA): `2 * EMA1 - EMA2`,
/// where EMA2 is the EMA of EMA1, both seeded as TA-Lib does.
///
/// Returns a float64 array with the same length as the input. Warm-up
/// positions are NaN.
#[pyfunction]
pub(crate) fn dema<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute(py, values, Params::Dema { period })
}

/// Calculates the DEMA of many datasets at once.
///
/// Returns a list in input order. Each entry is a float64 array, or the
/// exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn dema_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_batch(py, datasets, Params::Dema { period })
}
