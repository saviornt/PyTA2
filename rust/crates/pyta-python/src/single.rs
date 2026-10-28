use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1};
use pyo3::prelude::*;
use pyta_core::{Columns, IndicatorOutput, PytaResult, Series};
use pyta_engine::{IndicatorInput, IndicatorKind, IndicatorRequest, execute_direct};

use crate::error::to_python_error;

/// Copies and validates one array, with validation fused into the copy, so
/// the GIL can be released while another thread mutates the caller's array.
pub(crate) fn series_from(values: &PyReadonlyArray1<'_, f64>) -> PytaResult<Series> {
    // The Python layer always passes a C-contiguous array; the fallback
    // only guards direct callers of `_native`.
    match values.as_slice() {
        Ok(slice) => Series::from_slice(slice),
        Err(_) => Series::new(values.as_array().to_vec()),
    }
}

/// Copies and validates each column, in slot order, as [`series_from`] does.
pub(crate) fn columns_from(columns: &[PyReadonlyArray1<'_, f64>]) -> PytaResult<Columns> {
    Columns::new(columns.iter().map(series_from).collect::<PytaResult<_>>()?)
}

/// Executes one indicator request through the Rust engine.
fn calculate(
    input: IndicatorInput,
    period: usize,
    kind: IndicatorKind,
) -> PyResult<IndicatorOutput> {
    let request = IndicatorRequest {
        kind,
        input,
        period,
    };

    execute_direct(&request).map_err(to_python_error)
}

/// Releases the GIL, runs the engine, and returns a NumPy array.
fn run<'py>(
    py: Python<'py>,
    input: IndicatorInput,
    period: usize,
    kind: IndicatorKind,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let output = py.detach(move || calculate(input, period, kind))?;

    Ok(output.into_values().into_pyarray(py))
}

/// Copies and validates the input, releases the GIL, runs the engine,
/// and returns a NumPy array.
///
/// The input is copied once, with validation fused into the copy, so
/// the GIL can be released safely while another Python thread might
/// mutate the caller's array.
pub(crate) fn compute<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    period: usize,
    kind: IndicatorKind,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let input = series_from(&values).map_err(to_python_error)?;
    drop(values);

    run(py, IndicatorInput::Series(input), period, kind)
}

/// Like [`compute`], for a multi-column indicator: `columns` are the
/// indicator's input columns in slot order, each copied and validated once.
pub(crate) fn compute_columns<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    period: usize,
    kind: IndicatorKind,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let input = columns_from(&columns).map_err(to_python_error)?;
    drop(columns);

    run(py, IndicatorInput::Columns(input), period, kind)
}
