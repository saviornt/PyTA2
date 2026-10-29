use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates the Money Flow Index from high, low, close and volume.
///
/// `columns` are the high, low, close and volume arrays, in that order.
/// Returns a float64 array with the same length as the input, from 0 to 100.
/// Warm-up positions are NaN.
#[pyfunction]
pub(crate) fn mfi<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(py, columns, Params::Mfi { period })
}

/// Calculates the Money Flow Index of many datasets at once.
///
/// Each dataset is a list of its high, low, close and volume arrays. Returns
/// a list in input order. Each entry is a float64 array, or the exception
/// explaining why that dataset failed.
#[pyfunction]
pub(crate) fn mfi_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(py, datasets, Params::Mfi { period })
}
