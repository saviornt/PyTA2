use pyta_core::kernels::{for_each_window_max, for_each_window_min};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// The smallest `period` Aroon accepts (TA-Lib's lower bound).
const MIN_PERIOD: usize = 2;

/// Calculates Chande's Aroon Up, Aroon Down and Aroon Oscillator from high
/// and low, as TA-Lib 0.8.3's `TA_AROON` and `TA_AROONOSC`, in one pass per
/// column.
///
/// Each row looks back over a window of `period + 1` rows: the current row
/// and the `period` before it. With `factor = 100 / period`,
/// `aroon_up = factor * (period - rows since the highest high)` and
/// `aroon_down = factor * (period - rows since the lowest low)`; ties go to
/// the most recent row (TA-Lib's `>=` and `<=`). The oscillator is
/// `factor * (row of the highest high - row of the lowest low)`, exactly as
/// `TA_AROONOSC` writes it (not `aroon_up - aroon_down`, which can differ in
/// the last bit). The extremes come from `pyta_core::kernels`' rolling
/// extremes (van Herk/Gil-Werman, ties to the newest row), O(n) whatever the
/// period and the data, where TA-Lib's lazy rescan is O(n · period) on a
/// steadily falling high or rising low.
///
/// Returns three outputs, in order: Aroon Up, Aroon Down, Aroon Oscillator
/// (TA-Lib's `AROON` returns down before up). Each has the input's length,
/// and the first `period` positions of each are `NaN` (warm-up). At least
/// `period + 1` values are required.
///
/// Edge cases:
/// - A flat window: the current row is both the highest high and the lowest
///   low, so up and down are 100 and the oscillator 0.
/// - Every value is `100 / period` times a whole number of rows, from 0 to
///   100 (the oscillator from -100 to 100). For some periods (11, 22, 39,
///   ...) `(100 / period) * period` rounds to one ulp above or below 100,
///   and TA-Lib writes the same double.
///
/// The columns are not checked against each other (for example high
/// below low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidParameter` when `period` is below 2.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than `period + 1`
/// values.
pub fn aroon(high: &Series, low: &Series, period: usize) -> PytaResult<IndicatorOutput> {
    if period < MIN_PERIOD {
        return Err(PytaError::InvalidParameter {
            name: "period",
            minimum: MIN_PERIOD,
            value: period,
        });
    }

    let (high, low) = (high.values(), low.values());
    let length = high.len();

    if low.len() != length {
        return Err(PytaError::LengthMismatch);
    }

    // Saturates so a huge period from a direct `_native` call is reported,
    // not overflowed; the public API caps periods far below this.
    let required = period.saturating_add(1);

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    let factor = 100.0 / period as f64;
    let mut up = vec![f64::NAN; length];
    let mut down = vec![f64::NAN; length];
    let mut oscillator = vec![f64::NAN; length];

    // Row indices are far below 2^53, so as `f64` they and their
    // differences are exact, like TA-Lib's `int` arithmetic.
    for_each_window_max(high, required, |row, index| {
        up[row] = factor * (period - (row - index)) as f64;
        // Holds the highest high's row until the lows are walked.
        oscillator[row] = index as f64;
    });
    for_each_window_min(low, required, |row, index| {
        down[row] = factor * (period - (row - index)) as f64;
        oscillator[row] = factor * (oscillator[row] - index as f64);
    });

    IndicatorOutput::with_outputs(vec![up, down, oscillator])
}
