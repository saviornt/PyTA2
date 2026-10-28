use pyta_core::{Columns, IndicatorOutput, PytaError, PytaResult, Series};

/// Identifies an indicator supported by the engine.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndicatorKind {
    /// Commodity Channel Index (`pyta-momentum`; high, low, close).
    Cci,
    /// Relative Strength Index (`pyta-momentum`).
    Rsi,
    /// Simple Moving Average (`pyta-trend`).
    Sma,
}

/// The validated input of one request: one series, or several columns.
#[derive(Debug, Clone, PartialEq)]
pub enum IndicatorInput {
    /// Input of a single-column indicator.
    Series(Series),
    /// Input of a multi-column indicator, in its slot order.
    Columns(Columns),
}

impl IndicatorInput {
    /// Number of rows (never zero).
    pub fn len(&self) -> usize {
        match self {
            Self::Series(series) => series.len(),
            Self::Columns(columns) => columns.len(),
        }
    }

    /// Always false: every input has at least one row.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// The one series of a single-column input.
    ///
    /// A one-column `Columns` is accepted as well.
    ///
    /// # Errors
    ///
    /// `ColumnCount` when the input has several columns.
    pub fn series(&self) -> PytaResult<&Series> {
        let [series] = self.columns::<1>()?;

        Ok(series)
    }

    /// The `N` columns of a multi-column input, in slot order.
    ///
    /// # Errors
    ///
    /// `ColumnCount` when the input does not have exactly `N` columns.
    pub fn columns<const N: usize>(&self) -> PytaResult<[&Series; N]> {
        let columns = match self {
            Self::Series(series) => std::slice::from_ref(series),
            Self::Columns(columns) => columns.columns(),
        };

        <&[Series; N]>::try_from(columns)
            .map(<[Series; N]>::each_ref)
            .map_err(|_| PytaError::ColumnCount {
                expected: N,
                actual: columns.len(),
            })
    }
}

/// Describes one indicator calculation.
#[derive(Debug, Clone)]
pub struct IndicatorRequest {
    /// Which indicator to calculate.
    pub kind: IndicatorKind,
    /// The validated input.
    pub input: IndicatorInput,
    /// The indicator's period.
    pub period: usize,
}

impl IndicatorRequest {
    /// Creates a request for a single-column indicator.
    pub fn new(kind: IndicatorKind, input: Series, period: usize) -> Self {
        Self {
            kind,
            input: IndicatorInput::Series(input),
            period,
        }
    }

    /// Creates a request for a multi-column indicator; `input` is in the
    /// indicator's slot order.
    pub fn with_columns(kind: IndicatorKind, input: Columns, period: usize) -> Self {
        Self {
            kind,
            input: IndicatorInput::Columns(input),
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
