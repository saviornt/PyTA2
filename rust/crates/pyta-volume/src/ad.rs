use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

use crate::money_flow::money_flow_multiplier;

/// Calculates Marc Chaikin's Accumulation/Distribution line (A/D) from high,
/// low, close and volume, as TA-Lib 0.8.3's `TA_AD`.
///
/// Each row's money-flow volume is its money-flow multiplier
/// `((close - low) - (high - close)) / (high - low)` (from -1 at the low to
/// 1 at the high) times its volume; A/D is the running total of those
/// volumes, starting from 0, so row 0 already holds its own.
///
/// Returns one output with the input's length and no warm-up: every row has
/// a value, so one row is enough.
///
/// Edge cases, as TA-Lib 0.8.3:
/// - A row with `high - low` not above 0 (a one-price bar) adds nothing.
/// - A row with zero volume adds nothing.
/// - A close far outside a very narrow bar is not checked, so its multiplier
///   can be large and the total can overflow to `±inf`, as in TA-Lib; with
///   the close inside its bar every step is at most the row's volume.
///
/// Volume is not checked for sign here (the Python layer rejects negative
/// volume), nor high against low.
///
/// # Errors
///
/// Returns `LengthMismatch` when the columns differ in length.
pub fn ad(
    high: &Series,
    low: &Series,
    close: &Series,
    volume: &Series,
) -> PytaResult<IndicatorOutput> {
    let [high, low, close, volume] = [high.values(), low.values(), close.values(), volume.values()];
    let length = close.len();

    if [high, low, volume]
        .iter()
        .any(|column| column.len() != length)
    {
        return Err(PytaError::LengthMismatch);
    }

    let mut total = 0.0;
    let output = (0..length)
        .map(|row| {
            // TA-Lib's `ad += (close - low - (high - close)) / tmp * volume`.
            total += money_flow_multiplier(high[row], low[row], close[row]) * volume[row];
            total
        })
        .collect();

    Ok(IndicatorOutput::new(output))
}
