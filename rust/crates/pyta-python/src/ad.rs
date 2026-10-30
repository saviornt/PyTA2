use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates the Accumulation/Distribution line from high, low, close and
/// volume.
///
/// `columns` are the high, low, close and volume arrays, in that order.
/// Returns a float64 array with the same length as the input, with no
/// warm-up.
#[pyfunction]
pub(crate) fn ad<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(py, columns, Params::Ad)
}

/// Calculates the Accumulation/Distribution line of many datasets at once.
///
/// Each dataset is a list of its high, low, close and volume arrays. Returns
/// a list in input order. Each entry is a float64 array, or the exception
/// explaining why that dataset failed.
#[pyfunction]
pub(crate) fn ad_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(py, datasets, Params::Ad)
}
