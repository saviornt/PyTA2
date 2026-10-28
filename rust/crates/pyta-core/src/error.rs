// Shared error types for invalid input and calculation errors
use pyta_common::MAX_ABS_INPUT;
use thiserror::Error;

/// Errors shared across PyTA's Rust crates
#[derive(Debug, Clone, Error, PartialEq)]
pub enum PytaError {
    /// The input has no values.
    #[error("input series is empty; provide at least one value")]
    EmptyInput,

    /// A value is NaN or infinite.
    #[error(
        "non-finite value (NaN or infinity) at index {index}; only leading NaN values are skipped"
    )]
    NonFiniteValue {
        /// Position of the first offending value.
        index: usize,
    },

    /// A finite value exceeds [`MAX_ABS_INPUT`] in magnitude.
    #[error(
        "value at index {index} is too large in magnitude; values must be between -{limit:e} and {limit:e}",
        limit = MAX_ABS_INPUT
    )]
    ValueOutOfRange {
        /// Position of the first offending value.
        index: usize,
    },

    /// Series that must be aligned have different lengths.
    #[error("input series have mismatched lengths")]
    LengthMismatch,

    /// `period` is zero.
    #[error("period must be at least 1")]
    InvalidPeriod,

    /// `period` is longer than the series.
    #[error(
        "period ({period}) exceeds the series length ({length}); use a smaller period or provide more data"
    )]
    PeriodExceedsLength {
        /// The requested period.
        period: usize,
        /// The series length.
        length: usize,
    },

    /// The series is too short for the indicator.
    #[error("not enough data: at least {required} values are required, got {length}")]
    InsufficientData {
        /// The minimum number of values.
        required: usize,
        /// The series length.
        length: usize,
    },

    /// A request has the wrong number of input columns for its indicator.
    #[error("expected {expected} input columns, got {actual}")]
    ColumnCount {
        /// The number of columns the indicator takes.
        expected: usize,
        /// The number of columns given.
        actual: usize,
    },

    /// The calculation panicked; this is a bug in PyTA.
    #[error("indicator execution failed before returning a result")]
    ExecutionFailed,
}

/// Convenience alias for fallible PyTA operations.
pub type PytaResult<T> = Result<T, PytaError>;
