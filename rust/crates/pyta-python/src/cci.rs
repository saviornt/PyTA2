use numpy::{PyArray1, PyReadonlyArray1};
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::IndicatorKind;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates the Commodity Channel Index (CCI) from high, low and close.
///
/// `columns` are the high, low and close arrays, in that order. Returns a
/// float64 array with the same length as the input. Warm-up positions are NaN.
#[pyfunction]
pub(crate) fn cci<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    period: usize,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    compute_columns(py, columns, period, IndicatorKind::Cci)
}

/// Calculates the CCI of many datasets at once.
///
/// Each dataset is a list of its high, low and close arrays. Returns a list
/// in input order. Each entry is a float64 array, or the exception
/// explaining why that dataset failed.
#[pyfunction]
pub(crate) fn cci_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(py, datasets, period, IndicatorKind::Cci)
}
