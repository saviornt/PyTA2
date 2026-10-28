use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyta_core::PytaError;

/// Converts a PyTA error into a suitable Python exception.
///
/// Invalid input maps to `ValueError`; internal execution failures
/// map to `RuntimeError`.
#[expect(
    clippy::needless_pass_by_value,
    reason = "used as a `map_err` adapter, which passes the error by value"
)]
pub(crate) fn to_python_error(error: PytaError) -> PyErr {
    match error {
        PytaError::ExecutionFailed => PyRuntimeError::new_err(error.to_string()),
        _ => PyValueError::new_err(error.to_string()),
    }
}
