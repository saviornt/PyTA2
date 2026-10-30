use pyta_core::kernels::true_range_at;
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates Larry Williams' Ultimate Oscillator from high, low and close,
/// as TA-Lib 0.8.3's `TA_ULTOSC`.
///
/// Each row from 1 on has a buying pressure `BP = close - true low` and a
/// true range `TR` (`pyta_core::kernels::true_range_at`), the true low being
/// the lower of the low and the previous close. Over the last `short`,
/// `medium` and `long` rows (the current one included), the averages are
/// `sum(BP) / sum(TR)`, and
/// `ULTOSC = 100 * ((4 * A_short + 2 * A_medium + A_long) / 7)`, from 0 to
/// 100, in TA-Lib's order of operations.
///
/// Returns one output with the input's length; the first `long` positions
/// are `NaN` (warm-up: row 0 has no previous close). At least `long + 1`
/// rows are required.
///
/// Edge cases, as TA-Lib 0.8.3:
/// - A window whose true ranges sum to 0 drops its term; the divisor stays
///   7, so a fully flat stretch gives 0.
/// - The sums are kept by adding the new row and subtracting the one that
///   left, as TA-Lib does, so its rounding residue is reproduced; once a
///   window's worth of rows in a row have added nothing (both terms zero),
///   that window's sums are reset to exactly 0, as TA-Lib's are.
///
/// TA-Lib sorts the three periods silently; PyTA rejects them unless
/// `short < medium < long`. The columns are not checked against each other
/// (for example high below low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidParameter` when `short`, `medium` or `long` is zero.
/// Returns `ParametersOutOfOrder` when `short` is not below `medium` or
/// `medium` is not below `long`.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than `long + 1` rows.
pub fn ultosc(
    high: &Series,
    low: &Series,
    close: &Series,
    short: usize,
    medium: usize,
    long: usize,
) -> PytaResult<IndicatorOutput> {
    for (name, value) in [("short", short), ("medium", medium), ("long", long)] {
        if value == 0 {
            return Err(PytaError::InvalidParameter {
                name,
                minimum: 1,
                value,
            });
        }
    }
    for (lower, lower_value, upper, upper_value) in [
        ("short", short, "medium", medium),
        ("medium", medium, "long", long),
    ] {
        if lower_value >= upper_value {
            return Err(PytaError::ParametersOutOfOrder {
                lower,
                lower_value: lower_value as f64,
                upper,
                upper_value: upper_value as f64,
                strict: true,
            });
        }
    }

    let (high, low, close) = (high.values(), low.values(), close.values());

    if high.len() != close.len() || low.len() != close.len() {
        return Err(PytaError::LengthMismatch);
    }

    let length = close.len();
    // Saturates so a huge period from a direct `_native` call is reported,
    // not overflowed; the public API caps periods far below this.
    let required = long.saturating_add(1);

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    // Row `row`'s (buying pressure, true range).
    let terms = |row: usize| {
        let previous_close = close[row - 1];
        // TA-Lib's `min` macro: the previous close on a tie.
        let true_low = if low[row] < previous_close {
            low[row]
        } else {
            previous_close
        };
        (
            close[row] - true_low,
            true_range_at(high[row], low[row], previous_close),
        )
    };
    // Whether a row adds nothing to any sum (TA-Lib's `live` test).
    let is_null = |pressure: f64, range: f64| range + pressure.abs() <= 0.0;

    let (mut short_pressure, mut short_range) = (0.0, 0.0);
    let (mut medium_pressure, mut medium_range) = (0.0, 0.0);
    let (mut long_pressure, mut long_range) = (0.0, 0.0);
    // Consecutive rows that added nothing to any sum.
    let mut null_run = 0;
    // The terms of the last `long` rows, as TA-Lib's ring buffers: row `r`
    // sits in slot `(r - 1) % long`.
    let mut ring = vec![(0.0, 0.0); long];

    // The `long - 1` rows before the first output, each added to the
    // windows it falls in, in ascending order as TA-Lib does.
    for row in 1..long {
        let (pressure, range) = terms(row);
        ring[row - 1] = (pressure, range);
        null_run = if is_null(pressure, range) {
            null_run + 1
        } else {
            0
        };
        if row > long - short {
            short_pressure += pressure;
            short_range += range;
        }
        if row > long - medium {
            medium_pressure += pressure;
            medium_range += range;
        }
        long_pressure += pressure;
        long_range += range;
    }

    let mut output = vec![f64::NAN; length];
    // Ring slots of today and of the rows leaving each window after today.
    let mut current = long - 1;
    let (mut leaving_short, mut leaving_medium, mut leaving_long) =
        (long - short, long - medium, 0);
    let advance = |slot: usize| if slot + 1 == long { 0 } else { slot + 1 };

    for (today, slot) in output.iter_mut().enumerate().skip(long) {
        let (pressure, range) = terms(today);
        ring[current] = (pressure, range);
        current = advance(current);
        short_pressure += pressure;
        medium_pressure += pressure;
        long_pressure += pressure;
        short_range += range;
        medium_range += range;
        long_range += range;

        null_run = if is_null(pressure, range) {
            null_run + 1
        } else {
            0
        };
        // A window's worth of empty rows: its sums are exactly 0, so the
        // add-then-subtract residue is dropped. A run long enough for a
        // longer window is long enough for the shorter ones.
        if null_run >= short {
            (short_pressure, short_range) = (0.0, 0.0);
            if null_run >= medium {
                (medium_pressure, medium_range) = (0.0, 0.0);
                if null_run >= long {
                    null_run = long;
                    (long_pressure, long_range) = (0.0, 0.0);
                }
            }
        }

        // Each window contributes only when it holds a true range.
        let mut weighted = 0.0;
        if short_range > 0.0 {
            weighted += 4.0 * (short_pressure / short_range);
        }
        if medium_range > 0.0 {
            weighted += 2.0 * (medium_pressure / medium_range);
        }
        if long_range > 0.0 {
            weighted += long_pressure / long_range;
        }

        let (pressure, range) = ring[leaving_short];
        short_pressure -= pressure;
        short_range -= range;
        let (pressure, range) = ring[leaving_medium];
        medium_pressure -= pressure;
        medium_range -= range;
        let (pressure, range) = ring[leaving_long];
        long_pressure -= pressure;
        long_range -= range;
        leaving_short = advance(leaving_short);
        leaving_medium = advance(leaving_medium);
        leaving_long = advance(leaving_long);

        *slot = 100.0 * (weighted / 7.0);
    }

    Ok(IndicatorOutput::new(output))
}
