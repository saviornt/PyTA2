use std::sync::OnceLock;

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use pyta_core::{IndicatorOutput, PytaError, Series};
use pyta_engine::{
    execute_batch, IndicatorKind, IndicatorRequest, IndicatorStatus,
};
use tokio::runtime::{Builder, Runtime};

static RUNTIME: OnceLock<Result<Runtime, String>> = OnceLock::new();

/// Returns the shared Tokio runtime owned by the Python binding layer.
fn runtime() -> PyResult<&'static Runtime> {
    match RUNTIME.get_or_init(|| {
        Builder::new_multi_thread()
            .enable_all()
            .build()
            .map_err(|error| error.to_string())
    }) {
        Ok(runtime) => Ok(runtime),
        Err(message) => Err(PyRuntimeError::new_err(format!(
            "Failed to initialize PyTA's async runtime: {message}"
        ))),
    }
}

/// Converts a PyTA error into a suitable Python exception.
fn to_python_error(error: PytaError) -> PyErr {
    PyValueError::new_err(error.to_string())
}

/// Executes one indicator request through the Rust engine.
fn calculate(
    values: Vec<f64>,
    period: usize,
    kind: IndicatorKind,
) -> PyResult<IndicatorOutput> {
    let input = Series::new(values).map_err(to_python_error)?;
    let request = IndicatorRequest::new(kind, input, period);
    let runtime = runtime()?;

    let mut results = runtime.block_on(execute_batch(vec![request]));

    let result = results.pop().ok_or_else(|| {
        PyRuntimeError::new_err(
            "PyTA's engine returned no result for a single request",
        )
    })?;

    match result.status {
        IndicatorStatus::Success(output) => Ok(output),
        IndicatorStatus::Error(error) => Err(to_python_error(error)),
    }
}

/// Calculates the Simple Moving Average (SMA).
///
/// Returns a list with the same length as the input. Warm-up
/// positions contain None.
#[pyfunction]
fn sma(
    py: Python<'_>,
    values: Vec<f64>,
    period: usize,
) -> PyResult<Vec<Option<f64>>> {
    let output = py.detach(move || {
        calculate(values, period, IndicatorKind::Sma)
    })?;

    Ok(output.values().to_vec())
}

/// Calculates the Relative Strength Index (RSI) using Wilder's smoothing.
///
/// Returns a list with the same length as the input. Warm-up
/// positions contain None.
#[pyfunction]
fn rsi(
    py: Python<'_>,
    values: Vec<f64>,
    period: usize,
) -> PyResult<Vec<Option<f64>>> {
    let output = py.detach(move || {
        calculate(values, period, IndicatorKind::Rsi)
    })?;

    Ok(output.values().to_vec())
}

/// Native Python extension module: pyta._native
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sma, m)?)?;
    m.add_function(wrap_pyfunction!(rsi, m)?)?;
    Ok(())
}
