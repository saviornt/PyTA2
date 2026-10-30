use pyta_core::kernels::{CompensatedSum, typical_price_at};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates the Volume-Weighted Average Price (VWAP) from high, low, close
/// and volume, cumulative from the first row.
///
/// Each row's typical price `(high + low + close) / 3`
/// (`pyta_core::kernels::typical_price_at`) is weighted by its volume:
/// `VWAP = sum(typical price * volume) / sum(volume)` over every row so far.
/// There is no session reset (the input has no dates); a caller slices the
/// data per session to get the intraday convention.
///
/// Returns one output with the input's length. Rows before the first row
/// with volume are `NaN` (no volume, no average); from then on every row has
/// a value. One row is enough.
///
/// Edge cases:
/// - Zero volume on a later row leaves VWAP where it was.
/// - Both sums are compensated (Neumaier), so VWAP stays as accurate as a
///   fresh sum over any length of data.
/// - Price times volume is a product of two inputs, so near the input
///   magnitude limit it can overflow; the volume is then scaled by a power
///   of two, which changes no ratio, and the result stays finite.
///
/// Volume is not checked for sign here (the Python layer rejects negative
/// volume), nor high against low.
///
/// # Errors
///
/// Returns `LengthMismatch` when the columns differ in length.
pub fn vwap(
    high: &Series,
    low: &Series,
    close: &Series,
    volume: &Series,
) -> PytaResult<IndicatorOutput> {
    let columns = [high.values(), low.values(), close.values(), volume.values()];
    let length = columns[2].len();

    if columns.iter().any(|column| column.len() != length) {
        return Err(PytaError::LengthMismatch);
    }

    let mut output = vec![f64::NAN; length];

    if !cumulative_vwap(columns, 1.0, &mut output) {
        // Price times volume overflowed, which happens only near the input
        // magnitude limit. Run again with the volume scaled down by an exact
        // power of two, which leaves every ratio as it was (bit for bit,
        // unless a product becomes subnormal).
        let scale = overflow_scale(columns);
        cumulative_vwap(columns, scale, &mut output);
    }

    Ok(IndicatorOutput::new(output))
}

/// Writes VWAP from the first row with volume on, each row's volume
/// multiplied by `scale` (1 normally; an exact power of two after an
/// overflow). Returns whether the sums stayed finite.
fn cumulative_vwap(
    [high, low, close, volume]: [&[f64]; 4],
    scale: f64,
    output: &mut [f64],
) -> bool {
    let mut value = CompensatedSum::default();
    let mut traded = CompensatedSum::default();
    // Whether any row so far had volume (decided on the unscaled volume, so
    // a scaled-down tiny volume still counts).
    let mut started = false;

    for (row, slot) in output.iter_mut().enumerate() {
        let weight = volume[row] * scale;
        value.add(typical_price_at(high[row], low[row], close[row]) * weight);
        traded.add(weight);
        started |= volume[row] != 0.0;

        if started {
            *slot = value.value() / traded.value();
        }
    }

    // An overflowed product or sum stays infinite or NaN to the end.
    value.value().is_finite()
}

/// A power of two that brings the largest `|typical price| * |volume|` down
/// to about `2^960`, so the sums of up to `2^60` products stay finite.
fn overflow_scale([high, low, close, volume]: [&[f64]; 4]) -> f64 {
    let largest_price = (0..close.len())
        .map(|row| typical_price_at(high[row], low[row], close[row]).abs())
        .fold(0.0, f64::max);
    let largest_volume = volume.iter().map(|value| value.abs()).fold(0.0, f64::max);
    // Both are finite and, since their product overflowed, far above 1.
    let exponent = (largest_price.log2() + largest_volume.log2()).ceil() as i32;

    2.0_f64.powi(960 - exponent.max(960))
}
