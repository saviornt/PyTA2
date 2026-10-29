use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates Wilder's Average Directional Index (ADX) with +DI and -DI
/// from high, low and close, as TA-Lib's `TA_ADX`, `TA_PLUS_DI` and
/// `TA_MINUS_DI`.
///
/// `columns` are the high, low and close arrays, in that order. Returns a
/// list of three float64 arrays (ADX, +DI, -DI), each the same length as
/// the input. Warm-up positions are NaN: the DIs' first `period`, ADX's
/// first `2 * period - 1`.
#[pyfunction]
pub(crate) fn adx<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(py, columns, Params::Adx { period })
}

/// Calculates the ADX, +DI and -DI of many datasets at once.
///
/// Each dataset is a list of its high, low and close arrays. Returns a list
/// in input order. Each entry is a list of three float64 arrays (ADX, +DI,
/// -DI), or the exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn adx_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(py, datasets, Params::Adx { period })
}
