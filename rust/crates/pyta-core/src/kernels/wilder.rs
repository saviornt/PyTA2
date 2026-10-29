//! Wilder's smoothing, as an average (RSI, ATR) and as a running sum (ADX).

/// Wilder's smoothed average: `average * (n - 1) / n + value / n`.
///
/// This is RSI's form, with both weights computed once; TA-Lib writes
/// `(average * (n - 1) + value) / n`, which rounds differently in the last
/// bit but follows the same recurrence (the difference does not grow, since
/// each step shrinks the previous error by `(n - 1) / n`). The seed is the
/// caller's: Wilder and TA-Lib use the simple average of the first `n`
/// values.
#[derive(Clone, Copy, Debug)]
pub struct WilderAverage {
    value: f64,
    prior_weight: f64,
    current_weight: f64,
}

impl WilderAverage {
    /// Starts the average at `seed` for a smoothing period of `period`.
    ///
    /// The caller guarantees `period >= 1`.
    #[inline]
    #[must_use]
    pub fn new(period: usize, seed: f64) -> Self {
        debug_assert!(period >= 1);
        let period = period as f64;
        Self {
            value: seed,
            prior_weight: (period - 1.0) / period,
            current_weight: 1.0 / period,
        }
    }

    /// Adds `value` and returns the new average.
    #[inline]
    pub fn update(&mut self, value: f64) -> f64 {
        self.value = self.value * self.prior_weight + value * self.current_weight;
        self.value
    }

    /// The current average.
    #[inline]
    #[must_use]
    pub fn value(&self) -> f64 {
        self.value
    }
}

/// Wilder's smoothed sum: `sum - sum * (1 / n) + value`, TA-Lib 0.8.3's form
/// for ADX's directional movement and true range, in that order of
/// operations.
///
/// TA-Lib 0.8.3 multiplies by a precomputed `1 / n` (older releases divided
/// by `n`, which rounds differently in the last bit); this form matches the
/// 0.8.3 wheel's ADX, +DI and -DI bit for bit. It equals `n` times a
/// [`WilderAverage`] in exact arithmetic. The seed is the caller's (TA-Lib's
/// ADX starts from the sum of the first `n - 1` values and adds the `n`-th
/// through this update).
#[derive(Clone, Copy, Debug)]
pub struct WilderSum {
    sum: f64,
    inverse_period: f64,
}

impl WilderSum {
    /// Starts the sum at `seed` for a smoothing period of `period`.
    ///
    /// The caller guarantees `period >= 1`.
    #[must_use]
    pub fn new(period: usize, seed: f64) -> Self {
        debug_assert!(period >= 1);
        Self {
            sum: seed,
            inverse_period: 1.0 / period as f64,
        }
    }

    /// Adds `value` and returns the new sum.
    #[inline]
    pub fn update(&mut self, value: f64) -> f64 {
        self.sum = self.sum - self.sum * self.inverse_period + value;
        self.sum
    }

    /// The current sum.
    #[inline]
    #[must_use]
    pub fn value(&self) -> f64 {
        self.sum
    }
}

/// Writes Wilder's smoothed average of `values` to `output[start..]`,
/// leaving the positions before `start` as they are (ATR).
///
/// The seed, at `start`, is the simple average of the `period` values ending
/// there (a left-to-right sum divided by `period`), so a series whose first
/// value is undefined (true range) starts at `start = period`. Every later
/// value is [`WilderAverage::update`].
///
/// The caller guarantees `1 <= period <= start + 1 <= values.len()`,
/// `output.len() == values.len()`, and that `values[start + 1 - period..]`
/// holds no `NaN`.
pub fn wilder_into(values: &[f64], period: usize, start: usize, output: &mut [f64]) {
    debug_assert!(period >= 1 && period <= start + 1 && start < values.len());
    debug_assert_eq!(output.len(), values.len());

    let seed = values[start + 1 - period..=start].iter().sum::<f64>() / period as f64;
    let mut average = WilderAverage::new(period, seed);
    output[start] = seed;

    for (&value, slot) in values[start + 1..].iter().zip(&mut output[start + 1..]) {
        *slot = average.update(value);
    }
}
