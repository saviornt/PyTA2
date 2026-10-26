use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyta_core::{IndicatorOutput, PytaError, Series};
use pyta_engine::{IndicatorKind, IndicatorRequest, execute_direct};

/// Converts a PyTA error into a suitable Python exception.
///
/// Invalid input maps to `ValueError`; internal execution failures
/// map to `RuntimeError`.
fn to_python_error(error: PytaError) -> PyErr {
    match error {
        PytaError::ExecutionFailed => PyRuntimeError::new_err(error.to_string()),
        _ => PyValueError::new_err(error.to_string()),
    }
}

/// Executes one indicator request through the Rust engine.
fn calculate(values: Vec<f64>, period: usize, kind: IndicatorKind) -> PyResult<IndicatorOutput> {
    let input = Series::new(values).map_err(to_python_error)?;
    let request = IndicatorRequest::new(kind, input, period);

    execute_direct(&request).map_err(to_python_error)
}

/// Copies the input, releases the GIL, runs the engine, and returns a
/// NumPy array.
///
/// The input is copied once (a single memcpy) so the GIL can be
/// released safely while another Python thread might mutate the
/// caller's array.
fn compute<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
    kind: IndicatorKind,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let data = values.as_array().to_vec();
    drop(values);

    let output = py.detach(move || calculate(data, period, kind))?;

    Ok(output.into_values().into_pyarray(py))
}

/// Calculates the Simple Moving Average (SMA).
///
/// Returns a float64 array with the same length as the input. Warm-up
/// positions are NaN.
#[pyfunction]
fn sma<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    compute(py, values, period, IndicatorKind::Sma)
}

/// Calculates the Relative Strength Index (RSI) using Wilder's smoothing.
///
/// Returns a float64 array with the same length as the input. Warm-up
/// positions are NaN.
#[pyfunction]
fn rsi<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    compute(py, values, period, IndicatorKind::Rsi)
}

/// Native Python extension module: pyta._native
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sma, m)?)?;
    m.add_function(wrap_pyfunction!(rsi, m)?)?;
    Ok(())
}
