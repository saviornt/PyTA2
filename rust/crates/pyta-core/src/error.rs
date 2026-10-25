// Shared error types for invalid input and calculation errors
use thiserror::Error;

/// Errors shared across PyTA's Rust crates
#[derive(Debug, Clone, Error, PartialEq)]
pub enum PytaError {
    #[error("input series must not be empty")]
    EmptyInput,

    #[error("input contains a non-finite value at index {index}")]
    NonFiniteValue { index: usize },

    #[error("input series have mismatched lengths")]
    LengthMismatch,

    #[error("period must be greater than zero")]
    InvalidPeriod,

    #[error("period {period} exceeds input length {length}")]
    PeriodExceedsLength { period: usize, length: usize },

    #[error("invalid OHLCV data at index {index}: {reason}")]
    InvalidOhlcv { index: usize, reason: &'static str },

    #[error("indicator execution failed before returning a result")]
    ExecutionFailed
}

/// Convenience alias for fallible PyTA operations.
pub type PytaResult<T> = Result<T, PytaError>;