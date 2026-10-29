//! Core types and shared contracts for PyTA.

/// Errors shared by every PyTA crate.
pub mod error;
/// Validated input series.
pub mod input;
pub mod kernels;
/// Indicator results.
pub mod output;

pub use error::{PytaError, PytaResult};
pub use input::{Columns, Series};
pub use output::IndicatorOutput;
