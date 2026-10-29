use pyta_core::{Columns, IndicatorOutput, PytaError, PytaResult, Series};

/// Identifies an indicator supported by the engine, without its parameters.
///
/// Derived from [`Params::kind`], so a request's kind and parameters cannot
/// disagree. Used for logging and benchmark labels.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndicatorKind {
    /// Average Directional Index with +DI and -DI (`pyta-trend`; high, low,
    /// close; three outputs).
    Adx,
    /// Aroon Up, Aroon Down and Aroon Oscillator (`pyta-trend`; high, low;
    /// three outputs).
    Aroon,
    /// Average True Range (`pyta-volatility`; high, low, close).
    Atr,
    /// Bollinger Bands (`pyta-volatility`; three outputs).
    Bbands,
    /// Commodity Channel Index (`pyta-momentum`; high, low, close).
    Cci,
    /// Double Exponential Moving Average (`pyta-trend`).
    Dema,
    /// Donchian Channels (`pyta-volatility`; high, low; three outputs).
    Donchian,
    /// Exponential Moving Average (`pyta-trend`).
    Ema,
    /// Ichimoku Cloud, unshifted (`pyta-trend`; high, low, close; five
    /// outputs).
    Ichimoku,
    /// Kaufman Adaptive Moving Average (`pyta-trend`).
    Kama,
    /// Keltner Channels (`pyta-volatility`; high, low, close; three outputs).
    Keltner,
    /// Moving Average Convergence/Divergence (`pyta-trend`; three outputs).
    Macd,
    /// Relative Strength Index (`pyta-momentum`).
    Rsi,
    /// Parabolic SAR (`pyta-trend`; high, low).
    Sar,
    /// Simple Moving Average (`pyta-trend`).
    Sma,
    /// Standard Deviation (`pyta-volatility`).
    Stddev,
    /// Stochastic Oscillator, %K and %D (`pyta-momentum`; high, low, close;
    /// two outputs).
    Stoch,
    /// Triple Exponential Moving Average (`pyta-trend`).
    Tema,
    /// Weighted Moving Average (`pyta-trend`).
    Wma,
}

/// Which indicator to calculate, with its own parameters: one variant per
/// indicator.
///
/// Each dispatch arm destructures its own variant, so an indicator cannot
/// receive another's parameters. Adding a variant fails to compile until it
/// has a kind, a dispatch arm and a cost estimate. Python validates the
/// ranges first; the kernels still reject impossible values.
///
/// Fields may be `f64` (a multiplier such as Bollinger's `k`), so `Params` is
/// `PartialEq` but not `Eq` or `Hash`; a parameterless indicator is a unit
/// variant (`Obv`).
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Params {
    /// Average Directional Index, with +DI and -DI.
    Adx {
        /// Wilder's smoothing period of the directional movement, true range
        /// and ADX, at least 2.
        period: usize,
    },
    /// Aroon Up, Aroon Down and the Aroon Oscillator.
    Aroon {
        /// Rows looked back from the current row (a window of `period + 1`
        /// rows), at least 2.
        period: usize,
    },
    /// Average True Range.
    Atr {
        /// True ranges in the first average; Wilder's smoothing period.
        period: usize,
    },
    /// Bollinger Bands: an SMA with bands `k` population standard deviations
    /// above and below it.
    Bbands {
        /// Rows in each window, at least 2.
        period: usize,
        /// Width of each band in standard deviations, finite and above 0.
        k: f64,
    },
    /// Commodity Channel Index.
    Cci {
        /// Rows in each window.
        period: usize,
    },
    /// Double Exponential Moving Average: `2 * EMA - EMA of that EMA`.
    Dema {
        /// Period of both EMAs; sets their weight `2 / (period + 1)`.
        period: usize,
    },
    /// Donchian Channels: the highest high and lowest low of the last
    /// `period` rows, and their midpoint.
    Donchian {
        /// Rows in each window, the current row included.
        period: usize,
    },
    /// Exponential Moving Average.
    Ema {
        /// Rows in the seed average; sets the weight `2 / (period + 1)`.
        period: usize,
    },
    /// Ichimoku Cloud (Ichimoku Kinko Hyo): three window midpoints, the
    /// average of the first two, and close, each on the row it is
    /// calculated from (unshifted).
    Ichimoku {
        /// Rows in the tenkan-sen's (conversion line's) window, at least 1.
        tenkan: usize,
        /// Rows in the kijun-sen's (base line's) window, at least 1.
        kijun: usize,
        /// Rows in senkou span B's window, at least 1.
        senkou: usize,
    },
    /// Kaufman Adaptive Moving Average: an EMA whose weight follows the
    /// efficiency ratio of the last `period` rows (smoothing constants 2 and
    /// 30, fixed as in TA-Lib).
    Kama {
        /// Rows in the efficiency ratio's window.
        period: usize,
    },
    /// Keltner Channels: an EMA of close with bands `k` ATRs above and below
    /// it.
    Keltner {
        /// Rows in the EMA's seed average; sets its weight `2 / (period + 1)`.
        period: usize,
        /// The ATR's period (Wilder's smoothing).
        atr_period: usize,
        /// Width of each band in ATRs, finite and above 0.
        k: f64,
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
    /// Parabolic SAR (stop and reverse).
    Sar {
        /// The acceleration factor's start and its step, finite, above 0 and
        /// at most `maximum`.
        acceleration: f64,
        /// The acceleration factor's cap, finite and above 0.
        maximum: f64,
    },
    /// Simple Moving Average.
    Sma {
        /// Rows in each window.
        period: usize,
    },
    /// Standard Deviation (population), times a multiplier.
    Stddev {
        /// Rows in each window, at least 2.
        period: usize,
        /// Multiplier, finite and above 0.
        k: f64,
    },
    /// Stochastic Oscillator (full stochastic): raw %K over `k` rows,
    /// smoothed by an SMA over `k_smooth` rows (%K), and an SMA of %K over
    /// `d` rows (%D).
    Stoch {
        /// Rows in the highest-high and lowest-low window, at least 1.
        k: usize,
        /// Rows in the SMA that smooths raw %K, at least 1.
        k_smooth: usize,
        /// Rows in the SMA of %K that gives %D, at least 1.
        d: usize,
    },
    /// Triple Exponential Moving Average:
    /// `EMA3 + 3 * (EMA1 - EMA2)`, each EMA of the one before.
    Tema {
        /// Period of all three EMAs; sets their weight `2 / (period + 1)`.
        period: usize,
    },
    /// Weighted Moving Average: weights 1 (oldest) to `period` (newest).
    Wma {
        /// Rows in each window.
        period: usize,
    },
}

impl Params {
    /// The indicator these parameters belong to.
    pub fn kind(&self) -> IndicatorKind {
        match self {
            Self::Adx { .. } => IndicatorKind::Adx,
            Self::Aroon { .. } => IndicatorKind::Aroon,
            Self::Atr { .. } => IndicatorKind::Atr,
            Self::Bbands { .. } => IndicatorKind::Bbands,
            Self::Cci { .. } => IndicatorKind::Cci,
            Self::Dema { .. } => IndicatorKind::Dema,
            Self::Donchian { .. } => IndicatorKind::Donchian,
            Self::Ema { .. } => IndicatorKind::Ema,
            Self::Ichimoku { .. } => IndicatorKind::Ichimoku,
            Self::Kama { .. } => IndicatorKind::Kama,
            Self::Keltner { .. } => IndicatorKind::Keltner,
            Self::Macd { .. } => IndicatorKind::Macd,
            Self::Rsi { .. } => IndicatorKind::Rsi,
            Self::Sar { .. } => IndicatorKind::Sar,
            Self::Sma { .. } => IndicatorKind::Sma,
            Self::Stddev { .. } => IndicatorKind::Stddev,
            Self::Stoch { .. } => IndicatorKind::Stoch,
            Self::Tema { .. } => IndicatorKind::Tema,
            Self::Wma { .. } => IndicatorKind::Wma,
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
