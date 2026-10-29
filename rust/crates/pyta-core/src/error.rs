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

    /// An integer parameter is below its minimum: one other than `period`
    /// (`fast`), or a `period` whose minimum is above 1 (STDDEV's 2).
    #[error("{name} must be at least {minimum}, got {value}")]
    InvalidParameter {
        /// The parameter's name, as the caller knows it (`fast`, `signal`).
        name: &'static str,
        /// The smallest valid value.
        minimum: usize,
        /// The value given.
        value: usize,
    },

    /// A floating-point parameter is not a finite number above 0.
    #[error("{name} must be a finite number greater than 0, got {value}")]
    InvalidFloatParameter {
        /// The parameter's name, as the caller knows it (`k`).
        name: &'static str,
        /// The value given.
        value: f64,
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
