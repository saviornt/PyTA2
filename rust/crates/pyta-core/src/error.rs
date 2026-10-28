// Shared error types for invalid input and calculation errors
use pyta_common::MAX_ABS_INPUT;
use thiserror::Error;

/// Errors shared across PyTA's Rust crates
#[derive(Debug, Clone, Error, PartialEq)]
pub enum PytaError {
    #[error("input series is empty; provide at least one value")]
    EmptyInput,

    #[error(
        "non-finite value (NaN or infinity) at index {index}; only leading NaN values are skipped"
    )]
    NonFiniteValue { index: usize },

    #[error(
        "value at index {index} is too large in magnitude; values must be between -{limit:e} and {limit:e}",
        limit = MAX_ABS_INPUT
    )]
    ValueOutOfRange { index: usize },

    #[error("input series have mismatched lengths")]
    LengthMismatch,

    #[error("period must be at least 1")]
    InvalidPeriod,

    #[error(
        "period ({period}) exceeds the series length ({length}); use a smaller period or provide more data"
    )]
    PeriodExceedsLength { period: usize, length: usize },

    #[error("not enough data: at least {required} values are required, got {length}")]
    InsufficientData { required: usize, length: usize },

    #[error("invalid OHLCV data at index {index}: {reason}")]
    InvalidOhlcv { index: usize, reason: &'static str },

    #[error("indicator execution failed before returning a result")]
    ExecutionFailed,
}

/// Convenience alias for fallible PyTA operations.
pub type PytaResult<T> = Result<T, PytaError>;
