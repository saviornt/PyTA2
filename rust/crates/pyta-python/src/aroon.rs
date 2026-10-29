use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates Chande's Aroon Up, Aroon Down and Aroon Oscillator from high
/// and low, as TA-Lib's `TA_AROON` and `TA_AROONOSC`.
///
/// `columns` are the high and low arrays, in that order; each row looks
/// back over `period + 1` rows. Returns a list of three float64 arrays (up,
/// down, oscillator), each the same length as the input; the first
/// `period` values of each are NaN (warm-up).
#[pyfunction]
pub(crate) fn aroon<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(py, columns, Params::Aroon { period })
}

/// Calculates the Aroon Up, Aroon Down and Aroon Oscillator of many
/// datasets at once.
///
/// Each dataset is a list of its high and low arrays. Returns a list in
/// input order. Each entry is a list of three float64 arrays (up, down,
/// oscillator), or the exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn aroon_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(py, datasets, Params::Aroon { period })
}
