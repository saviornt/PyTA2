//! Native Python extension module: `pyta._native`.
//!
//! This file only declares the modules and registers their functions with
//! Python. Shared plumbing lives in `error`, `single`, and `batch`; each
//! indicator's bindings live in a file named after it.

mod batch;
mod error;
mod rsi;
mod single;
mod sma;

use pyo3::prelude::*;

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sma::sma, m)?)?;
    m.add_function(wrap_pyfunction!(sma::sma_batch, m)?)?;
    m.add_function(wrap_pyfunction!(rsi::rsi, m)?)?;
    m.add_function(wrap_pyfunction!(rsi::rsi_batch, m)?)?;
    Ok(())
}
