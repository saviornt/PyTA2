//! Native Python extension module: `pyta._native`.
//!
//! This file only declares the modules and registers their functions with
//! Python. Shared plumbing lives in `error`, `single`, `batch`, and
//! `log_bridge` (Rust `log` records to Python `logging`); each
//! indicator's bindings live in a file named after it.

mod atr;
mod batch;
mod cci;
mod ema;
mod error;
mod log_bridge;
mod macd;
mod rsi;
mod single;
mod sma;
mod stddev;

use pyo3::prelude::*;

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    log_bridge::init(m.py());
    m.add("MAX_ABS_INPUT", pyta_common::MAX_ABS_INPUT)?;
    m.add_function(wrap_pyfunction!(atr::atr, m)?)?;
    m.add_function(wrap_pyfunction!(atr::atr_batch, m)?)?;
    m.add_function(wrap_pyfunction!(cci::cci, m)?)?;
    m.add_function(wrap_pyfunction!(cci::cci_batch, m)?)?;
    m.add_function(wrap_pyfunction!(sma::sma, m)?)?;
    m.add_function(wrap_pyfunction!(sma::sma_batch, m)?)?;
    m.add_function(wrap_pyfunction!(rsi::rsi, m)?)?;
    m.add_function(wrap_pyfunction!(rsi::rsi_batch, m)?)?;
    m.add_function(wrap_pyfunction!(ema::ema, m)?)?;
    m.add_function(wrap_pyfunction!(ema::ema_batch, m)?)?;
    m.add_function(wrap_pyfunction!(macd::macd, m)?)?;
    m.add_function(wrap_pyfunction!(macd::macd_batch, m)?)?;
    m.add_function(wrap_pyfunction!(stddev::stddev, m)?)?;
    m.add_function(wrap_pyfunction!(stddev::stddev_batch, m)?)?;
    Ok(())
}
