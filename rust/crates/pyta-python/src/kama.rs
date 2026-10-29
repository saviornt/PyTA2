use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_batch;
use crate::single::compute;

/// Calculates Kaufman's Adaptive Moving Average (KAMA): an EMA whose weight
/// follows the efficiency ratio of the last `period` rows, as TA-Lib's
/// `TA_KAMA`.
///
/// Returns a float64 array with the same length as the input. Warm-up
/// positions are NaN.
#[pyfunction]
pub(crate) fn kama<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute(py, values, Params::Kama { period })
}

/// Calculates the KAMA of many datasets at once.
///
/// Returns a list in input order. Each entry is a float64 array, or the
/// exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn kama_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    period: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_batch(py, datasets, Params::Kama { period })
}
