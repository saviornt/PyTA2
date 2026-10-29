use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_engine::Params;

use crate::batch::compute_columns_batch;
use crate::single::compute_columns;

/// Calculates Wilder's Parabolic SAR (stop and reverse) from high and low,
/// as TA-Lib's `TA_SAR`.
///
/// `columns` are the high and low arrays, in that order. `acceleration` is
/// the acceleration factor's start and step, `maximum` its cap. Returns one
/// float64 array the same length as the input; the first value is NaN
/// (warm-up).
#[pyfunction]
pub(crate) fn sar<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    acceleration: f64,
    maximum: f64,
) -> PyResult<Bound<'py, PyAny>> {
    compute_columns(
        py,
        columns,
        Params::Sar {
            acceleration,
            maximum,
        },
    )
}

/// Calculates the Parabolic SAR of many datasets at once.
///
/// Each dataset is a list of its high and low arrays. Returns a list in
/// input order. Each entry is a float64 array, or the exception explaining
/// why that dataset failed.
#[pyfunction]
pub(crate) fn sar_batch<'py>(
    py: Python<'py>,
    datasets: &Bound<'py, PyList>,
    acceleration: f64,
    maximum: f64,
) -> PyResult<Bound<'py, PyList>> {
    compute_columns_batch(
        py,
        datasets,
        Params::Sar {
            acceleration,
            maximum,
        },
    )
}
