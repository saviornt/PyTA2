use numpy::{IntoPyArray, PyReadonlyArray1};
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyta_core::{Columns, IndicatorOutput, PytaResult, Series};
use pyta_engine::{IndicatorInput, IndicatorRequest, Params, execute_direct};

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

/// Converts an indicator's output to Python without copying: a float64
/// array for a single-output indicator, or a list of float64 arrays in the
/// indicator's documented order for a multi-output one.
///
/// Every indicator has a fixed number of outputs, so each binding always
/// returns the same shape.
pub(crate) fn output_to_python(
    py: Python<'_>,
    output: IndicatorOutput,
) -> PyResult<Bound<'_, PyAny>> {
    if output.output_count() == 1 {
        return Ok(output.into_values().into_pyarray(py).into_any());
    }

    let arrays = output
        .into_outputs()
        .into_iter()
        .map(|values| values.into_pyarray(py));

    Ok(PyList::new(py, arrays)?.into_any())
}

/// Releases the GIL, runs the engine, and converts the output to Python.
fn run<'py>(py: Python<'py>, input: IndicatorInput, params: Params) -> PyResult<Bound<'py, PyAny>> {
    let request = IndicatorRequest { input, params };
    let output = py.detach(move || execute_direct(&request).map_err(to_python_error))?;

    output_to_python(py, output)
}

/// Copies and validates the input, releases the GIL, runs the engine,
/// and returns a NumPy array (or a list of them, for a multi-output
/// indicator; see [`output_to_python`]).
///
/// The input is copied once, with validation fused into the copy, so
/// the GIL can be released safely while another Python thread might
/// mutate the caller's array.
pub(crate) fn compute<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    params: Params,
) -> PyResult<Bound<'py, PyAny>> {
    let input = series_from(&values).map_err(to_python_error)?;
    drop(values);

    run(py, IndicatorInput::Series(input), params)
}

/// Like [`compute`], for a multi-column indicator: `columns` are the
/// indicator's input columns in slot order, each copied and validated once.
pub(crate) fn compute_columns<'py>(
    py: Python<'py>,
    columns: Vec<PyReadonlyArray1<'py, f64>>,
    params: Params,
) -> PyResult<Bound<'py, PyAny>> {
    let input = columns_from(&columns).map_err(to_python_error)?;
    drop(columns);

    run(py, IndicatorInput::Columns(input), params)
}
