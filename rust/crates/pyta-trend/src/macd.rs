use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

use crate::ema::ema_into;

/// Calculates Moving Average Convergence/Divergence (MACD), as TA-Lib's
/// `TA_MACD`.
///
/// Returns three outputs, in this order:
/// 1. `macd`: the fast EMA minus the slow EMA, from index `slow - 1`.
/// 2. signal: the `signal`-period EMA of the `macd` line, from index
///    `slow + signal - 2`.
/// 3. histogram: `macd` minus signal, from index `slow + signal - 2`.
///
/// Both EMAs start at index `slow - 1`: the slow one is seeded with the
/// simple average of the first `slow` values and the fast one with the
/// simple average of the `fast` values ending there (TA-Lib's seeding). The
/// signal EMA is seeded with the simple average of the first `signal` values
/// of the `macd` line. Each output is `NaN` before its own start; TA-Lib
/// also blanks `macd` until the signal starts, PyTA keeps those values.
///
/// When `slow < fast` the two are swapped, as TA-Lib does, and `fast ==
/// slow` gives zeros after the warm-up.
///
/// # Errors
///
/// Returns `InvalidParameter` when `fast` or `slow` is below 2 or `signal`
/// is below 1 (TA-Lib's ranges), naming the parameter as given.
/// Returns `InsufficientData` when the input has fewer than
/// `slow + signal - 1` values (after any swap), so every output has a value.
pub fn macd(
    input: &Series,
    fast: usize,
    slow: usize,
    signal: usize,
) -> PytaResult<IndicatorOutput> {
    for (name, minimum, value) in [("fast", 2, fast), ("slow", 2, slow), ("signal", 1, signal)] {
        if value < minimum {
            return Err(PytaError::InvalidParameter {
                name,
                minimum,
                value,
            });
        }
    }

    let (fast, slow) = if slow < fast {
        (slow, fast)
    } else {
        (fast, slow)
    };

    let values = input.values();
    let length = values.len();
    // Saturates so a huge period from a direct `_native` call is reported,
    // not overflowed; the public API caps periods far below this.
    let required = slow.saturating_add(signal - 1);

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    let macd_start = slow - 1;
    let signal_start = slow + signal - 2;

    // The slow EMA goes to `line` and the fast one to `histogram`, so the
    // three outputs are the only allocations.
    let mut line = vec![f64::NAN; length];
    let mut signal_line = vec![f64::NAN; length];
    let mut histogram = vec![f64::NAN; length];

    ema_into(values, slow, macd_start, &mut line);
    ema_into(values, fast, macd_start, &mut histogram);

    for (slow_ema, fast_ema) in line[macd_start..].iter_mut().zip(&histogram[macd_start..]) {
        *slow_ema = fast_ema - *slow_ema;
    }

    ema_into(&line, signal, signal_start, &mut signal_line);

    histogram[macd_start..signal_start].fill(f64::NAN);
    for ((hist, macd), signal) in histogram[signal_start..]
        .iter_mut()
        .zip(&line[signal_start..])
        .zip(&signal_line[signal_start..])
    {
        *hist = macd - signal;
    }

    IndicatorOutput::with_outputs(vec![line, signal_line, histogram])
}
