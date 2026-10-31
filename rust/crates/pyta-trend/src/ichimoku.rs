use pyta_core::kernels::{for_each_window_min, rolling_max};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// Calculates Goichi Hosoda's Ichimoku Kinko Hyo (Ichimoku Cloud) from high,
/// low and close, unshifted unless `shift` is set. Ichimoku is not a TA-Lib
/// function.
///
/// Unshifted, each line is on the row it is calculated from, with windows
/// that include the current row:
/// - tenkan-sen (conversion line): `(highest high + lowest low) / 2` over
///   the last `tenkan` rows;
/// - kijun-sen (base line): the same over `kijun` rows;
/// - senkou span A (leading span A): `(tenkan-sen + kijun-sen) / 2`;
/// - senkou span B (leading span B): the midpoint over `senkou` rows;
/// - chikou span (lagging span): close.
///
/// The midpoints use `pyta_core::kernels`' rolling extremes (O(n) whatever
/// the window) and are computed exactly as Donchian Channels' middle line,
/// so tenkan-sen equals Donchian's middle over `tenkan` rows bit for bit.
///
/// With `shift`, the outputs take the layout charts draw, displaced by
/// `kijun` rows (Hosoda's 26 is the kijun period) and still as long as the
/// input: the value of either senkou span calculated on row `t` is written
/// on row `t + kijun` (the first `kijun` rows are `NaN`, and the values of
/// the last `kijun` rows, the future cloud, fall off the end), and row `t`
/// of the chikou span holds the close of row `t + kijun` (the last `kijun`
/// rows are `NaN`). The tenkan-sen and kijun-sen do not move. When `kijun`
/// is at least the input's length, both spans and the chikou span are all
/// `NaN`.
///
/// Returns five outputs, in order: tenkan-sen, kijun-sen, senkou span A,
/// senkou span B, chikou span. Each has the same length as the input and
/// keeps its own warm-up: unshifted, the first `tenkan - 1`, `kijun - 1`,
/// `max(tenkan, kijun) - 1` and `senkou - 1` positions of the first four
/// are `NaN`, and the chikou span has none; shifted, the spans' warm-ups
/// grow by `kijun`. At least `max(tenkan, kijun, senkou)` values are
/// required (with or without `shift`), so every unshifted output has a
/// value.
///
/// Edge cases:
/// - A window of 1: that line is `(high + low) / 2` on each row.
/// - A flat window (or high equal to low throughout it): the line is that
///   level.
///
/// The columns are not checked against each other (for example high
/// below low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidParameter` when `tenkan`, `kijun` or `senkou` is zero.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than
/// `max(tenkan, kijun, senkou)` values.
pub fn ichimoku(
    high: &Series,
    low: &Series,
    close: &Series,
    tenkan: usize,
    kijun: usize,
    senkou: usize,
    shift: bool,
) -> PytaResult<IndicatorOutput> {
    for (name, value) in [("tenkan", tenkan), ("kijun", kijun), ("senkou", senkou)] {
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
    let required = tenkan.max(kijun).max(senkou);

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    let tenkan_sen = midpoint(high, low, tenkan);
    let kijun_sen = midpoint(high, low, kijun);
    let mut senkou_b = midpoint(high, low, senkou);
    let mut senkou_a = vec![f64::NAN; length];
    let start = tenkan.max(kijun) - 1;

    for ((span, &conversion), &base) in senkou_a[start..]
        .iter_mut()
        .zip(&tenkan_sen[start..])
        .zip(&kijun_sen[start..])
    {
        *span = (conversion + base) / 2.0;
    }

    let chikou = if shift {
        shift_forward(&mut senkou_a, kijun);
        shift_forward(&mut senkou_b, kijun);
        let mut chikou = vec![f64::NAN; length];
        if kijun < length {
            chikou[..length - kijun].copy_from_slice(&close[kijun..]);
        }
        chikou
    } else {
        close.to_vec()
    };

    IndicatorOutput::with_outputs(vec![tenkan_sen, kijun_sen, senkou_a, senkou_b, chikou])
}

/// Moves `values` `rows` positions later in place, filling the first `rows`
/// with `NaN` and dropping the last `rows` values (all `NaN` when `rows` is
/// at least the length).
fn shift_forward(values: &mut [f64], rows: usize) {
    let length = values.len();
    let kept = length.saturating_sub(rows);
    values.copy_within(..kept, length - kept);
    values[..length - kept].fill(f64::NAN);
}

/// `(highest high + lowest low) / 2` over each `period`-row window, with
/// `NaN` in the first `period - 1` positions: Donchian's middle line, in
/// one buffer.
///
/// The caller guarantees `1 <= period <= high.len() == low.len()`.
fn midpoint(high: &[f64], low: &[f64], period: usize) -> Vec<f64> {
    let mut middle = rolling_max(high, period);

    // Inputs are at most `MAX_ABS_INPUT` (1e290), so the sum stays finite.
    for_each_window_min(low, period, |row, index| {
        middle[row] = (middle[row] + low[index]) / 2.0;
    });
    middle
}
