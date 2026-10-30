use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_batch;
use crate::single::compute;

/// Calculates TRIX: the one-row rate of change, in percent, of a triple EMA
/// (each EMA of the one before, all of `period`), 0 when the previous value
/// is 0, as TA-Lib does.
///
/// Returns a float64 array with the same length as the input. Warm-up
/// positions are NaN.
#[pyfunction]
pub(crate) fn trix<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute(py, values, Params::Trix { period })
}

/// Calculates the TRIX of many datasets at once.
///
/// Returns a list in input order. Each entry is a float64 array, or the
/// exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn trix_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_batch(py, datasets, Params::Trix { period })
}
