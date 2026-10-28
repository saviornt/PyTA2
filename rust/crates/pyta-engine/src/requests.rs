use pyta_core::{IndicatorOutput, PytaError, Series};

/// Identifies an indicator supported by the engine.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndicatorKind {
    /// Relative Strength Index (`pyta-momentum`).
    Rsi,
    /// Simple Moving Average (`pyta-trend`).
    Sma,
}

/// Describes one indicator calculation.
#[derive(Debug, Clone)]
pub struct IndicatorRequest {
    /// Which indicator to calculate.
    pub kind: IndicatorKind,
    /// The validated input series.
    pub input: Series,
    /// The indicator's period.
    pub period: usize,
}

impl IndicatorRequest {
    /// Creates a request for a single-series indicator.
    pub fn new(kind: IndicatorKind, input: Series, period: usize) -> Self {
        Self {
            kind,
            input,
            period,
        }
    }
}

/// The outcome of one indicator calculation.
#[derive(Debug, Clone, PartialEq)]
pub enum IndicatorStatus {
    /// The calculated values.
    Success(IndicatorOutput),
    /// Why the calculation failed.
    Error(PytaError),
}

/// Associates an outcome with its original position in a batch.
#[derive(Debug, Clone, PartialEq)]
pub struct IndicatorResult {
    /// Position of the request in its batch.
    pub index: usize,
    /// The outcome.
    pub status: IndicatorStatus,
}

impl IndicatorResult {
    /// A successful result for the request at `index`.
    pub fn success(index: usize, output: IndicatorOutput) -> Self {
        Self {
            index,
            status: IndicatorStatus::Success(output),
        }
    }

    /// A failed result for the request at `index`.
    pub fn error(index: usize, error: PytaError) -> Self {
        Self {
            index,
            status: IndicatorStatus::Error(error),
        }
    }

    /// Whether the calculation succeeded.
    pub fn is_success(&self) -> bool {
        matches!(self.status, IndicatorStatus::Success(_))
    }

    /// Whether the calculation failed.
    pub fn is_error(&self) -> bool {
        matches!(self.status, IndicatorStatus::Error(_))
    }
}
