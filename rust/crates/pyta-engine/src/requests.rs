use pyta_core::{IndicatorOutput, PytaError, Series};

/// Identifies an indicator supported by the engine.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndicatorKind {
    Rsi,
    Sma,
}

/// Describes one indicator calculation.
#[derive(Debug, Clone)]
pub struct IndicatorRequest {
    pub kind: IndicatorKind,
    pub input: Series,
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
    Success(IndicatorOutput),
    Error(PytaError),
}

/// Associates an outcome with its original position in a batch.
#[derive(Debug, Clone, PartialEq)]
pub struct IndicatorResult {
    pub index: usize,
    pub status: IndicatorStatus,
}

impl IndicatorResult {
    pub fn success(index: usize, output: IndicatorOutput) -> Self {
        Self {
            index,
            status: IndicatorStatus::Success(output),
        }
    }

    pub fn error(index: usize, error: PytaError) -> Self {
        Self {
            index,
            status: IndicatorStatus::Error(error),
        }
    }

    pub fn is_success(&self) -> bool {
        matches!(self.status, IndicatorStatus::Success(_))
    }

    pub fn is_error(&self) -> bool {
        matches!(self.status, IndicatorStatus::Error(_))
    }
}
