use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates Williams %R from high, low and close.
///
/// `columns` are the high, low and close arrays, in that order. Returns a
/// float64 array with the same length as the input, from -100 to 0. Warm-up
/// positions are NaN.
#[pyfunction]
pub(crate) fn willr<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(py, columns, Params::Willr { period })
}

/// Calculates the Williams %R of many datasets at once.
///
/// Each dataset is a list of its high, low and close arrays. Returns a list
/// in input order. Each entry is a float64 array, or the exception
/// explaining why that dataset failed.
#[pyfunction]
pub(crate) fn willr_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(py, datasets, Params::Willr { period })
}
