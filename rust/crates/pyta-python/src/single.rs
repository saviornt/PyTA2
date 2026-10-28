use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1};
use pyo3::prelude::*;
use pyta_core::{IndicatorOutput, Series};
use pyta_engine::{IndicatorKind, IndicatorRequest, execute_direct};

use crate::error::to_python_error;

/// Executes one indicator request through the Rust engine.
fn calculate(input: Series, period: usize, kind: IndicatorKind) -> PyResult<IndicatorOutput> {
    let request = IndicatorRequest::new(kind, input, period);

    execute_direct(&request).map_err(to_python_error)
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
    // The Python layer always passes a C-contiguous array; the fallback
    // only guards direct callers of `_native`.
    let input = match values.as_slice() {
        Ok(slice) => Series::from_slice(slice),
        Err(_) => Series::new(values.as_array().to_vec()),
    }
    .map_err(to_python_error)?;
    drop(values);

    let output = py.detach(move || calculate(input, period, kind))?;

    Ok(output.into_values().into_pyarray(py))
}
