use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_batch;
use crate::single::compute;

/// Calculates Moving Average Convergence/Divergence (MACD), as TA-Lib does.
///
/// Returns a list of three float64 arrays, each the length of the input:
/// the MACD line, the signal line and the histogram. Warm-up positions are
/// NaN: the MACD line starts at `slow - 1`, the others at
/// `slow + signal - 2`. When `slow < fast` the two are swapped.
#[pyfunction]
pub(crate) fn macd<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    fast: usize,
    slow: usize,
    signal: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute(py, values, Params::Macd { fast, slow, signal })
}

/// Calculates the MACD of many datasets at once.
///
/// Returns a list in input order. Each entry is a list of the three arrays,
/// or the exception explaining why that dataset failed.
#[pyfunction]
pub(crate) fn macd_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    fast: usize,
    slow: usize,
    signal: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_batch(py, datasets, Params::Macd { fast, slow, signal })
}
