use pyta_core::{Columns, IndicatorOutput, PytaError, PytaResult, Series};

/// Identifies an indicator supported by the engine, without its parameters.
///
/// Derived from [`Params::kind`], so a request's kind and parameters cannot
/// disagree. Used for logging and benchmark labels.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndicatorKind {
    /// Commodity Channel Index (`pyta-momentum`; high, low, close).
    Cci,
    /// Exponential Moving Average (`pyta-trend`).
    Ema,
    /// Moving Average Convergence/Divergence (`pyta-trend`; three outputs).
    Macd,
    /// Relative Strength Index (`pyta-momentum`).
    Rsi,
    /// Simple Moving Average (`pyta-trend`).
    Sma,
}

/// Which indicator to calculate, with its own parameters: one variant per
/// indicator.
///
/// Each dispatch arm destructures its own variant, so an indicator cannot
/// receive another's parameters. Adding a variant fails to compile until it
/// has a kind, a dispatch arm and a cost estimate. Python validates the
/// ranges first; the kernels still reject impossible values.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Params {
    /// Commodity Channel Index.
    Cci {
        /// Rows in each window.
        period: usize,
    },
    /// Exponential Moving Average.
    Ema {
        /// Rows in the seed average; sets the weight `2 / (period + 1)`.
        period: usize,
    },
    /// Moving Average Convergence/Divergence.
    Macd {
        /// Period of the fast EMA.
        fast: usize,
        /// Period of the slow EMA (swapped with `fast` when smaller).
        slow: usize,
        /// Period of the signal line's EMA.
        signal: usize,
    },
    /// Relative Strength Index.
    Rsi {
        /// Price changes in the first average.
        period: usize,
    },
    /// Simple Moving Average.
    Sma {
        /// Rows in each window.
        period: usize,
    },
}

impl Params {
    /// The indicator these parameters belong to.
    pub fn kind(&self) -> IndicatorKind {
        match self {
            Self::Cci { .. } => IndicatorKind::Cci,
            Self::Ema { .. } => IndicatorKind::Ema,
            Self::Macd { .. } => IndicatorKind::Macd,
            Self::Rsi { .. } => IndicatorKind::Rsi,
            Self::Sma { .. } => IndicatorKind::Sma,
        }
    }
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
    /// The validated input.
    pub input: IndicatorInput,
    /// Which indicator to calculate, with its parameters.
    pub params: Params,
}

impl IndicatorRequest {
    /// Creates a request for a single-column indicator, such as
    /// `IndicatorRequest::new(series, Params::Rsi { period: 14 })`.
    pub fn new(input: Series, params: Params) -> Self {
        Self {
            input: IndicatorInput::Series(input),
            params,
        }
    }

    /// Creates a request for a multi-column indicator; `input` is in the
    /// indicator's slot order.
    pub fn with_columns(input: Columns, params: Params) -> Self {
        Self {
            input: IndicatorInput::Columns(input),
            params,
        }
    }

    /// The indicator to calculate.
    pub fn kind(&self) -> IndicatorKind {
        self.params.kind()
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
