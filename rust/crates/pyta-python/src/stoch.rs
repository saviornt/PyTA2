use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates the Stochastic Oscillator (full stochastic) from high, low and
/// close: raw %K over `k` rows, smoothed by an SMA over `k_smooth` rows
/// (%K), and an SMA of %K over `d` rows (%D).
///
/// `columns` are the high, low and close arrays, in that order. Returns a
/// list of two float64 arrays (%K, %D), each the same length as the input.
/// Warm-up positions are NaN: the first `k + k_smooth - 2` of %K and the
/// first `k + k_smooth + d - 3` of %D.
#[pyfunction]
pub(crate) fn stoch<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    k: usize,
    k_smooth: usize,
    d: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(py, columns, Params::Stoch { k, k_smooth, d })
}

/// Calculates the Stochastic Oscillator of many datasets at once.
///
/// Each dataset is a list of its high, low and close arrays. Returns a list
/// in input order. Each entry is a list of two float64 arrays (%K, %D), or
/// the exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn stoch_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    k: usize,
    k_smooth: usize,
    d: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(py, datasets, Params::Stoch { k, k_smooth, d })
}
