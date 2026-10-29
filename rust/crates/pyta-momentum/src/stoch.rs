use pyta_core::kernels::{for_each_window_max, for_each_window_min, is_zero_scaled};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates George Lane's Stochastic Oscillator (the full stochastic,
/// %K and %D) from high, low and close, as TA-Lib's `TA_STOCH` 0.8.3 does
/// with simple moving averages.
///
/// - Raw %K on each row:
///   `(close - lowest low) / (highest high - lowest low) * 100`, the
///   extremes over the last `k` rows, the current row included.
///   On a flat window (the range is zero next to `|highest| + |lowest|`,
///   TA-Lib's `TA_IS_ZERO_SCALED`) raw %K is 0.
/// - `stoch_k`: the simple moving average of raw %K over `k_smooth` rows.
/// - `stoch_d`: the simple moving average of `stoch_k` over `d` rows.
///
/// Both averages use TA-Lib's running sum (add the new value, take the
/// total, subtract the oldest, divide by the period), so a %D over a flat
/// stretch keeps the sum's rounding residue (about `1e-14`) rather than
/// reading exactly 0, as TA-Lib's does. With `k_smooth = 1` `stoch_k` is
/// the fast (raw) %K; Lane's slow stochastic is `k_smooth = 3`, `d = 3`.
///
/// Returns two outputs, in order: `stoch_k`, `stoch_d`. Each has the same
/// length as the input and keeps its own warm-up: the first
/// `k + k_smooth - 2` positions of `stoch_k` and the first
/// `k + k_smooth + d - 3` of `stoch_d` are `NaN` (TA-Lib also blanks
/// `stoch_k` until `stoch_d` has a value; PyTA does not). At least
/// `k + k_smooth + d - 2` values are required, so both outputs have a value.
///
/// The columns are not checked against each other (for example high below
/// low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidParameter` when `k`, `k_smooth` or `d` is zero.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than
/// `k + k_smooth + d - 2` values.
pub fn stoch(
    high: &Series,
    low: &Series,
    close: &Series,
    k: usize,
    k_smooth: usize,
    d: usize,
) -> PytaResult<IndicatorOutput> {
    for (name, value) in [("k", k), ("k_smooth", k_smooth), ("d", d)] {
        if value == 0 {
            return Err(PytaError::InvalidParameter {
                name,
                minimum: 1,
                value,
            });
        }
    }

    let (high, low, close) = (high.values(), low.values(), close.values());

    if high.len() != close.len() || low.len() != close.len() {
        return Err(PytaError::LengthMismatch);
    }

    let length = close.len();
    let required = k.saturating_add(k_smooth).saturating_add(d) - 2;

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    let k_start = k + k_smooth - 2;
    let d_start = k_start + d - 1;
    let mut stoch_k = vec![f64::NAN; length];
    let mut stoch_d = vec![f64::NAN; length];

    // Raw %K is parked in `stoch_d` from row `k - 1` (no extra buffer): the
    // highest high first, then the ratio once the lowest low is known.
    let raw = &mut stoch_d[k - 1..];
    for_each_window_max(high, k, |row, index| raw[row + 1 - k] = high[index]);
    for_each_window_min(low, k, |row, index| {
        let (highest, lowest) = (raw[row + 1 - k], low[index]);
        let range = highest - lowest;

        raw[row + 1 - k] = if is_zero_scaled(range, highest.abs() + lowest.abs()) {
            0.0
        } else {
            (close[row] - lowest) / range * 100.0
        };
    });

    talib_sma_into(&stoch_d[k - 1..], k_smooth, &mut stoch_k[k_start..]);
    // Raw %K is no longer needed: clear what lies before %D's first value.
    stoch_d[k - 1..d_start].fill(f64::NAN);
    talib_sma_into(&stoch_k[k_start..], d, &mut stoch_d[d_start..]);

    IndicatorOutput::with_outputs(vec![stoch_k, stoch_d])
}

/// Writes the `period`-value simple moving averages of `values` to `means`
/// (`means[i]` the mean of `values[i..i + period]`) with TA-Lib's
/// `TA_INT_SMA` arithmetic: a plain running total that gains the newest
/// value, is read, then loses the oldest, divided by `period`.
///
/// The caller guarantees `1 <= period <= values.len()` and
/// `means.len() == values.len() - period + 1`.
fn talib_sma_into(values: &[f64], period: usize, means: &mut [f64]) {
    debug_assert!(period >= 1 && period <= values.len());
    debug_assert_eq!(means.len(), values.len() - period + 1);

    let divisor = period as f64;
    let mut total: f64 = values[..period - 1].iter().sum();

    for ((mean, &newest), &oldest) in means.iter_mut().zip(&values[period - 1..]).zip(values) {
        total += newest;
        *mean = total / divisor;
        total -= oldest;
    }
}
