use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// The rows SAR needs: the first only seeds the direction and the SAR.
const REQUIRED: usize = 2;

/// Calculates Wilder's Parabolic SAR (stop and reverse) from high and low,
/// as TA-Lib 0.8.3's `TA_SAR`.
///
/// The first direction comes from row 1's directional movement, as
/// TA-Lib's `TA_MINUS_DM` with period 1: short when the low fell (`low[0] -
/// low[1] > 0`) by more than the high rose, else long (a tie is long). A
/// long start takes `low[0]` as its SAR and `high[1]` as its extreme point
/// (EP); a short one `high[0]` and `low[1]`. The acceleration factor (AF)
/// starts at `acceleration`.
///
/// Each row from 1 writes the SAR carried into it, unless the row reverses
/// the trade: a long one when its low is at or below the SAR, a short one
/// when its high is at or above it. On a reversal the SAR becomes the EP,
/// moved out to the previous and current row's high (long to short) or low
/// (short to long) if it lies inside them, and that value is written; then
/// AF resets to `acceleration` and EP to the row's low (now short) or high
/// (now long). Without a reversal, a new extreme sets EP and raises AF by
/// `acceleration`, capped at `maximum`. Either way the next SAR is
/// `SAR + AF * (EP - SAR)`, kept outside the previous and current row's
/// lows (long) or highs (short). On row 1 the "previous row" is row 1
/// itself, as TA-Lib does.
///
/// Returns one output with the input's length; row 0 is `NaN` (warm-up)
/// and every later row has a value. At least 2 rows are required.
///
/// TA-Lib writes the step as `fma(af, ep - sar, sar)`; this kernel uses
/// the plain multiply-add (faster without a `+fma` target feature), so a
/// few values differ from TA-Lib 0.8.3's in the last bit.
///
/// The columns are not checked against each other (for example high
/// below low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidFloatParameter` when `acceleration` or `maximum` is not
/// a finite number above 0.
/// Returns `ParametersOutOfOrder` when `acceleration` is above `maximum`
/// (TA-Lib lowers `acceleration` to `maximum` instead).
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than 2 rows.
pub fn sar(
    high: &Series,
    low: &Series,
    acceleration: f64,
    maximum: f64,
) -> PytaResult<IndicatorOutput> {
    for (name, value) in [("acceleration", acceleration), ("maximum", maximum)] {
        // Also false for NaN.
        if !(value > 0.0 && value.is_finite()) {
            return Err(PytaError::InvalidFloatParameter { name, value });
        }
    }
    if acceleration > maximum {
        return Err(PytaError::ParametersOutOfOrder {
            lower: "acceleration",
            lower_value: acceleration,
            upper: "maximum",
            upper_value: maximum,
        });
    }

    let (high, low) = (high.values(), low.values());
    let length = high.len();

    if low.len() != length {
        return Err(PytaError::LengthMismatch);
    }
    if length < REQUIRED {
        return Err(PytaError::InsufficientData {
            required: REQUIRED,
            length,
        });
    }

    let mut output = vec![f64::NAN; length];

    // TA-Lib's -DM over rows 0 and 1: positive only when the low's fall
    // beats the high's rise.
    let rise = high[1] - high[0];
    let fall = low[0] - low[1];
    let mut is_long = !(fall > 0.0 && rise < fall);

    let (mut sar, mut extreme) = if is_long {
        (low[0], high[1])
    } else {
        (high[0], low[1])
    };
    let mut factor = acceleration;
    // TA-Lib's "previous row" on the first step is row 1 itself.
    let (mut new_high, mut new_low) = (high[1], low[1]);

    for (index, slot) in output.iter_mut().enumerate().skip(1) {
        let (previous_high, previous_low) = (new_high, new_low);
        (new_high, new_low) = (high[index], low[index]);

        if is_long {
            if new_low <= sar {
                is_long = false;
                sar = at_least(extreme, previous_high, new_high);
                *slot = sar;

                factor = acceleration;
                extreme = new_low;
                sar = at_least(factor * (extreme - sar) + sar, previous_high, new_high);
            } else {
                *slot = sar;

                if new_high > extreme {
                    extreme = new_high;
                    factor = capped(factor + acceleration, maximum);
                }
                sar = at_most(factor * (extreme - sar) + sar, previous_low, new_low);
            }
        } else if new_high >= sar {
            is_long = true;
            sar = at_most(extreme, previous_low, new_low);
            *slot = sar;

            factor = acceleration;
            extreme = new_high;
            sar = at_most(factor * (extreme - sar) + sar, previous_low, new_low);
        } else {
            *slot = sar;

            if new_low < extreme {
                extreme = new_low;
                factor = capped(factor + acceleration, maximum);
            }
            sar = at_least(factor * (extreme - sar) + sar, previous_high, new_high);
        }
    }

    Ok(IndicatorOutput::new(output))
}

/// `value` raised to `first`, then to `second`, as TA-Lib's two `if`s
/// (`if (sar < prevHigh) sar = prevHigh;`).
fn at_least(value: f64, first: f64, second: f64) -> f64 {
    let value = if value < first { first } else { value };
    if value < second { second } else { value }
}

/// `value` lowered to `first`, then to `second`, as TA-Lib's two `if`s.
fn at_most(value: f64, first: f64, second: f64) -> f64 {
    let value = if value > first { first } else { value };
    if value > second { second } else { value }
}

/// The acceleration factor capped at `maximum`, as TA-Lib's `if`.
fn capped(factor: f64, maximum: f64) -> f64 {
    if factor > maximum { maximum } else { factor }
}
