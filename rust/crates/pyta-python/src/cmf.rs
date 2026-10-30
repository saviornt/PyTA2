use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates Chaikin Money Flow from high, low, close and volume.
///
/// `columns` are the high, low, close and volume arrays, in that order.
/// Returns a float64 array with the same length as the input, from -1 to 1.
/// Warm-up positions, and windows without volume, are NaN.
#[pyfunction]
pub(crate) fn cmf<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(py, columns, Params::Cmf { period })
}

/// Calculates Chaikin Money Flow of many datasets at once.
///
/// Each dataset is a list of its high, low, close and volume arrays. Returns
/// a list in input order. Each entry is a float64 array, or the exception
/// explaining why that dataset failed.
#[pyfunction]
pub(crate) fn cmf_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(py, datasets, Params::Cmf { period })
}
