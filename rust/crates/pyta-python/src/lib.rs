//! Native Python extension module: `pyta._native`.
//!
//! This file only declares the modules and registers their functions with
//! Python. Shared plumbing lives in `error`, `single`, `batch`, and
//! `log_bridge` (Rust `log` records to Python `logging`); each
//! indicator's bindings live in a file named after it.

mod adx;
mod aroon;
mod atr;
mod batch;
mod bbands;
mod cci;
mod dema;
mod donchian;
mod ema;
mod error;
mod kama;
mod keltner;
mod log_bridge;
mod macd;
mod rsi;
mod sar;
mod single;
mod sma;
mod stddev;
mod tema;
mod wma;

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
    m.add_function(wrap_pyfunction!(wma::wma, m)?)?;
    m.add_function(wrap_pyfunction!(wma::wma_batch, m)?)?;
    m.add_function(wrap_pyfunction!(dema::dema, m)?)?;
    m.add_function(wrap_pyfunction!(dema::dema_batch, m)?)?;
    m.add_function(wrap_pyfunction!(tema::tema, m)?)?;
    m.add_function(wrap_pyfunction!(tema::tema_batch, m)?)?;
    m.add_function(wrap_pyfunction!(kama::kama, m)?)?;
    m.add_function(wrap_pyfunction!(kama::kama_batch, m)?)?;
    m.add_function(wrap_pyfunction!(adx::adx, m)?)?;
    m.add_function(wrap_pyfunction!(adx::adx_batch, m)?)?;
    m.add_function(wrap_pyfunction!(aroon::aroon, m)?)?;
    m.add_function(wrap_pyfunction!(aroon::aroon_batch, m)?)?;
    m.add_function(wrap_pyfunction!(sar::sar, m)?)?;
    m.add_function(wrap_pyfunction!(sar::sar_batch, m)?)?;
    m.add_function(wrap_pyfunction!(macd::macd, m)?)?;
    m.add_function(wrap_pyfunction!(macd::macd_batch, m)?)?;
    m.add_function(wrap_pyfunction!(stddev::stddev, m)?)?;
    m.add_function(wrap_pyfunction!(stddev::stddev_batch, m)?)?;
    m.add_function(wrap_pyfunction!(bbands::bbands, m)?)?;
    m.add_function(wrap_pyfunction!(bbands::bbands_batch, m)?)?;
    m.add_function(wrap_pyfunction!(donchian::donchian, m)?)?;
    m.add_function(wrap_pyfunction!(donchian::donchian_batch, m)?)?;
    m.add_function(wrap_pyfunction!(keltner::keltner, m)?)?;
    m.add_function(wrap_pyfunction!(keltner::keltner_batch, m)?)?;
    Ok(())
}
