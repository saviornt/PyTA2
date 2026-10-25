 //! Core types and shared contracts for PyTA.

pub mod error;
pub mod input;
pub mod output;

pub use error::{PytaError, PytaResult};
pub use input::{Ohlcv, Series};
pub use output::IndicatorOutput;
