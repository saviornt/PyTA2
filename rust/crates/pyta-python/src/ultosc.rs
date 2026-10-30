use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates the Ultimate Oscillator from high, low and close: buying
/// pressure over true range in windows of `short`, `medium` and `long`
/// rows, weighted 4, 2 and 1.
///
/// `columns` are the high, low and close arrays, in that order. Returns a
/// float64 array with the same length as the input, from 0 to 100. Warm-up
/// positions are NaN.
#[pyfunction]
pub(crate) fn ultosc<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    short: usize,
    medium: usize,
    long: usize,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(
        py,
        columns,
        Params::Ultosc {
            short,
            medium,
            long,
        },
    )
}

/// Calculates the Ultimate Oscillator of many datasets at once.
///
/// Each dataset is a list of its high, low and close arrays. Returns a list
/// in input order. Each entry is a float64 array, or the exception
/// explaining why that dataset failed.
#[pyfunction]
pub(crate) fn ultosc_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    short: usize,
    medium: usize,
    long: usize,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(
        py,
        datasets,
        Params::Ultosc {
            short,
            medium,
            long,
        },
    )
}
