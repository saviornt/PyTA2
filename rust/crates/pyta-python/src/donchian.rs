use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates Donchian Channels from high and low: the highest high and
/// lowest low of the last `period` rows (the current row included) and
/// their midpoint.
///
/// `columns` are the high and low arrays, in that order. Returns a list of
/// three float64 arrays (upper, middle, lower), each the same length as the
/// input. Warm-up positions are NaN.
#[pyfunction]
pub(crate) fn donchian<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(py, columns, Params::Donchian { period })
}

/// Calculates the Donchian Channels of many datasets at once.
///
/// Each dataset is a list of its high and low arrays. Returns a list in
/// input order. Each entry is a list of three float64 arrays (upper, middle,
/// lower), or the exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn donchian_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(py, datasets, Params::Donchian { period })
}
