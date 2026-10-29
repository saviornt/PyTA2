use pyta_core::kernels::{ema_multiplier, ema_step};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

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

    // One pass for all three EMAs, kept here rather than three calls to
    // `kernels::ema_into` because the fused loop is 2.1-2.3x faster. Every
    // update is the shared `ema_step` and every seed a left-to-right sum
    // divided by the period, as in `ema_into`, so the results are bit for bit
    // those of one EMA pass after another.
    let fast_k = ema_multiplier(fast);
    let slow_k = ema_multiplier(slow);
    let signal_k = ema_multiplier(signal);

    let mut slow_ema = values[..slow].iter().sum::<f64>() / slow as f64;
    let mut fast_ema = values[slow - fast..slow].iter().sum::<f64>() / fast as f64;

    // Each output gets its warm-up `NaN`s, then is pushed to once per row.
    let mut line = Vec::with_capacity(length);
    line.resize(macd_start, f64::NAN);
    line.push(fast_ema - slow_ema);

    // Until the signal starts, only the `macd` line has values.
    for value in &values[slow..=signal_start] {
        slow_ema = ema_step(slow_ema, *value, slow_k);
        fast_ema = ema_step(fast_ema, *value, fast_k);
        line.push(fast_ema - slow_ema);
    }

    let mut signal_ema = line[macd_start..].iter().sum::<f64>() / signal as f64;

    let mut signal_line = Vec::with_capacity(length);
    signal_line.resize(signal_start, f64::NAN);
    signal_line.push(signal_ema);

    let mut histogram = Vec::with_capacity(length);
    histogram.resize(signal_start, f64::NAN);
    histogram.push(line[signal_start] - signal_ema);

    for value in &values[signal_start + 1..] {
        slow_ema = ema_step(slow_ema, *value, slow_k);
        fast_ema = ema_step(fast_ema, *value, fast_k);
        let macd = fast_ema - slow_ema;
        signal_ema = ema_step(signal_ema, macd, signal_k);

        line.push(macd);
        signal_line.push(signal_ema);
        histogram.push(macd - signal_ema);
    }

    IndicatorOutput::with_outputs(vec![line, signal_line, histogram])
}
