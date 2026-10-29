use pyta_core::kernels::{true_range, wilder_into};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates the Average True Range (ATR), following TA-Lib's `TA_ATR`.
///
/// The true range of a row is the largest of `high - low`,
/// `|high - previous close|` and `|low - previous close|`
/// (`pyta_core::kernels::true_range`); the first row has no previous close,
/// so it has none. The first ATR, at row `period`, is the mean of the true
/// ranges of rows `1..=period`; each later one is Wilder's smoothing of the
/// previous ATR and the row's true range
/// (`pyta_core::kernels::WilderAverage`). At least `period + 1` values are
/// required.
///
/// The output has the same length as the input. The first `period`
/// positions are `NaN` (warm-up).
///
/// Edge cases:
/// - A flat series (or high equal to low with an unchanged close): ATR 0.
/// - `period` of 1: ATR is the true range, from row 1.
///
/// The columns are not checked against each other (for example high
/// below low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than
/// `period + 1` values.
pub fn atr(
    high: &Series,
    low: &Series,
    close: &Series,
    period: usize,
) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let (high, low, close) = (high.values(), low.values(), close.values());

    if high.len() != close.len() || low.len() != close.len() {
        return Err(PytaError::LengthMismatch);
    }

    if period >= close.len() {
        return Err(PytaError::InsufficientData {
            required: period + 1,
            length: close.len(),
        });
    }

    // Row 0's true range is NaN; the seed at row `period` averages rows
    // `1..=period`, so it never reads it.
    let ranges = true_range(high, low, close);
    let mut output = vec![f64::NAN; ranges.len()];
    wilder_into(&ranges, period, period, &mut output);

    Ok(IndicatorOutput::new(output))
}
