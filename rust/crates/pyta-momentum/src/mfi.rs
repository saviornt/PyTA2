use pyta_core::kernels::{is_zero_scaled, typical_price_at};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// The smallest `period` MFI accepts (TA-Lib's lower bound).
const MIN_PERIOD: usize = 2;

/// Calculates Gene Quong and Avrum Soudack's Money Flow Index (MFI) from
/// high, low, close and volume, as TA-Lib 0.8.3's `TA_MFI`.
///
/// Each row's money flow is its typical price `(high + low + close) / 3`
/// (`pyta_core::kernels::typical_price_at`) times its volume. It counts as
/// positive when the typical price rose from the previous row, negative when
/// it fell, and as neither when it is unchanged within rounding (the change
/// is zero next to the two typical prices' `|a| + |b|`, TA-Lib's
/// `TA_IS_ZERO_SCALED`). The positive and negative flows of the last
/// `period` rows are summed and `MFI = 100 * positive / (positive +
/// negative)`, from 0 to 100.
///
/// Returns one output with the input's length; the first `period` positions
/// are `NaN` (warm-up: row 0 has no previous typical price). At least
/// `period + 1` rows are required.
///
/// Edge cases, as TA-Lib 0.8.3:
/// - A window with no money flow at all (every typical price unchanged, or
///   no volume) gives 0.
/// - The sums are kept by adding the new row and subtracting the one that
///   left, as TA-Lib does, so its rounding residue is reproduced; once
///   `period` rows in a row have added nothing, both sums are reset to
///   exactly 0, as TA-Lib's are.
/// - The positive sum is clamped into `[0, total]` before dividing, so the
///   result stays within 0 to 100.
/// - Price times volume is a product of two inputs, so near the input
///   magnitude limit it can overflow; the volume is then scaled by a power
///   of two, which changes no ratio, and the result stays finite.
///
/// Volume is not checked for sign here (the Python layer rejects negative
/// volume), nor high against low.
///
/// # Errors
///
/// Returns `InvalidParameter` when `period` is below 2.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than `period + 1`
/// rows.
pub fn mfi(
    high: &Series,
    low: &Series,
    close: &Series,
    volume: &Series,
    period: usize,
) -> PytaResult<IndicatorOutput> {
    if period < MIN_PERIOD {
        return Err(PytaError::InvalidParameter {
            name: "period",
            minimum: MIN_PERIOD,
            value: period,
        });
    }

    let columns = [high.values(), low.values(), close.values(), volume.values()];
    let length = columns[2].len();

    if columns.iter().any(|column| column.len() != length) {
        return Err(PytaError::LengthMismatch);
    }

    // Saturates so a huge period from a direct `_native` call is reported,
    // not overflowed; the public API caps periods far below this.
    let required = period.saturating_add(1);

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    let mut output = vec![f64::NAN; length];

    if !money_flow_index(columns, period, 1.0, &mut output) {
        // Price times volume overflowed, which happens only near the input
        // magnitude limit. Run again with the volume scaled down by an exact
        // power of two, which leaves every ratio as it was (bit for bit,
        // unless a flow becomes subnormal).
        let scale = overflow_scale(columns);
        money_flow_index(columns, period, scale, &mut output);
    }

    Ok(IndicatorOutput::new(output))
}

/// Writes MFI from row `period` on, each row's volume multiplied by `scale`
/// (1 normally; an exact power of two after an overflow). Returns whether
/// every total stayed finite.
fn money_flow_index(
    [high, low, close, volume]: [&[f64]; 4],
    period: usize,
    scale: f64,
    output: &mut [f64],
) -> bool {
    // The (positive, negative) flows of the last `period` rows, as TA-Lib's
    // ring buffers: row `r` sits in slot `(r - 1) % period`, so the slot
    // about to be written holds the row leaving the window.
    let mut ring = vec![(0.0, 0.0); period];
    let mut slot = 0;
    let (mut positive, mut negative) = (0.0, 0.0);
    let mut previous = typical_price_at(high[0], low[0], close[0]);
    // Consecutive rows that added nothing to either sum.
    let mut null_run = 0;
    let mut finite = true;

    for row in 1..output.len() {
        if row > period {
            let (leaving_positive, leaving_negative) = ring[slot];
            positive -= leaving_positive;
            negative -= leaving_negative;
        }

        let current = typical_price_at(high[row], low[row], close[row]);
        let change = current - previous;
        let money_flow = if is_zero_scaled(change, current.abs() + previous.abs()) {
            0.0
        } else {
            current * (volume[row] * scale)
        };
        previous = current;

        let flows = if change < 0.0 {
            (0.0, money_flow)
        } else {
            (money_flow, 0.0)
        };
        ring[slot] = flows;
        slot = if slot + 1 == period { 0 } else { slot + 1 };
        positive += flows.0;
        negative += flows.1;

        null_run = if money_flow == 0.0 { null_run + 1 } else { 0 };
        if null_run >= period {
            // A whole window of empty rows: both sums are exactly 0, so the
            // add-then-subtract residue is dropped.
            null_run = period;
            positive = 0.0;
            negative = 0.0;
        }

        if row >= period {
            let total = positive + negative;
            finite &= total.is_finite();
            // TA-Lib's `total <= 0.0` test, written so that an overflowed
            // (NaN) total, which is recomputed anyway, cannot reach `clamp`.
            output[row] = if total > 0.0 {
                100.0 * (positive.clamp(0.0, total) / total)
            } else {
                0.0
            };
        }
    }

    finite
}

/// A power of two that brings the largest `|typical price| * |volume|` down
/// to about `2^960`, so the sums of up to `2^60` flows stay finite.
fn overflow_scale([high, low, close, volume]: [&[f64]; 4]) -> f64 {
    let largest_price = (0..close.len())
        .map(|row| typical_price_at(high[row], low[row], close[row]).abs())
        .fold(0.0, f64::max);
    let largest_volume = volume.iter().map(|value| value.abs()).fold(0.0, f64::max);
    // Both are finite and, since their product overflowed, far above 1.
    let exponent = (largest_price.log2() + largest_volume.log2()).ceil() as i32;

    2.0_f64.powi(960 - exponent.max(960))
}
