use pyta_core::kernels::{CompensatedSum, two_sum};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

use crate::money_flow::money_flow_multiplier;

/// Calculates Marc Chaikin's Chaikin Money Flow (CMF) from high, low, close
/// and volume.
///
/// Each row's money-flow volume is its money-flow multiplier
/// `((close - low) - (high - close)) / (high - low)` times its volume, as in
/// Accumulation/Distribution (the same crate-private helper, so a one-price
/// bar has a multiplier of 0). Over the last `period` rows, the current row
/// included, `CMF = sum(money-flow volume) / sum(volume)`, from -1 to 1 when
/// every close lies inside its bar.
///
/// Returns one output with the input's length; the first `period - 1`
/// positions are `NaN` (warm-up). At least `period` rows are required.
///
/// Edge cases:
/// - A window whose volume is all zero gives `NaN` (the ratio is undefined;
///   TA-Lib has no CMF to follow). Zero volume elsewhere is valid.
/// - The two window sums are kept by adding the new row and subtracting the
///   leaving one with Knuth's two-sum and Neumaier compensation, so they stay
///   as accurate as fresh window sums however long the input; whether a
///   window is empty is decided by a count of its non-zero volumes, never by
///   a rounded sum.
///
/// Volume is not checked for sign here (the Python layer rejects negative
/// volume), nor high against low.
///
/// # Errors
///
/// Returns `InvalidPeriod` when `period` is zero.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `PeriodExceedsLength` when `period` exceeds the input length.
pub fn cmf(
    high: &Series,
    low: &Series,
    close: &Series,
    volume: &Series,
    period: usize,
) -> PytaResult<IndicatorOutput> {
    if period == 0 {
        return Err(PytaError::InvalidPeriod);
    }

    let [high, low, close, volume] = [high.values(), low.values(), close.values(), volume.values()];
    let length = close.len();

    if [high, low, volume]
        .iter()
        .any(|column| column.len() != length)
    {
        return Err(PytaError::LengthMismatch);
    }

    if period > length {
        return Err(PytaError::PeriodExceedsLength { period, length });
    }

    let mut output = vec![f64::NAN; length];
    // The money-flow volumes of the last `period` rows: row `r` sits in slot
    // `r % period`, so the slot about to be written holds the leaving row.
    let mut ring = vec![0.0; period];
    let mut flow = CompensatedSum::default();
    let mut traded = CompensatedSum::default();
    // Rows in the window with non-zero volume.
    let mut active = 0_usize;

    for row in 0..length {
        let slot = row % period;
        let money_flow = money_flow_multiplier(high[row], low[row], close[row]) * volume[row];

        if row < period {
            flow.add(money_flow);
            traded.add(volume[row]);
        } else {
            let leaving = row - period;
            // `new - old` exactly: the rounded difference and its error.
            let (change, error) = two_sum(money_flow, -ring[slot]);
            flow.add_with_error(change, error);
            let (change, error) = two_sum(volume[row], -volume[leaving]);
            traded.add_with_error(change, error);
            active -= usize::from(volume[leaving] != 0.0);
        }
        ring[slot] = money_flow;
        active += usize::from(volume[row] != 0.0);

        if row + 1 >= period && active > 0 {
            output[row] = flow.value() / traded.value();
        }
    }

    Ok(IndicatorOutput::new(output))
}
