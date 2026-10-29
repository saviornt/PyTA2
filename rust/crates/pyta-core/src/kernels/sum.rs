//! Accurate and fast summation helpers.

/// A running sum with Neumaier-style compensation: each addition's rounding
/// error is computed exactly (Knuth's two-sum) and kept apart, so the total
/// stays as accurate as a fresh sum however many values pass through.
#[derive(Clone, Copy, Debug, Default)]
pub struct CompensatedSum {
    sum: f64,
    compensation: f64,
}

impl CompensatedSum {
    /// Adds `value`.
    #[inline]
    pub fn add(&mut self, value: f64) {
        let (total, error) = two_sum(self.sum, value);
        self.compensation += error;
        self.sum = total;
    }

    /// Adds `value` whose own rounding error is `error`, as returned by
    /// [`two_sum`] when `value` was formed: a window that gains one value and
    /// loses another adds their exact difference this way, one dependent
    /// addition per row.
    #[inline]
    pub fn add_with_error(&mut self, value: f64, error: f64) {
        self.add(value);
        self.compensation += error;
    }

    /// The compensated total.
    #[inline]
    #[must_use]
    pub fn value(&self) -> f64 {
        self.sum + self.compensation
    }
}

/// `a + b` and its rounding error exactly (Knuth's two-sum): `a + b` equals
/// the two results added in exact arithmetic. Exact whichever operand is
/// larger, so no branch is needed.
#[inline]
#[must_use]
pub fn two_sum(a: f64, b: f64) -> (f64, f64) {
    let total = a + b;
    let b_part = total - a;
    let a_part = total - b_part;
    (total, (a - a_part) + (b - b_part))
}

/// Sums `term(x)` over `values` with `LANES` independent totals, so the
/// additions overlap instead of each waiting for the last (see
/// `pyta_common::kernels` for the lane counts and their measurements).
#[inline]
pub fn lane_sum<const LANES: usize>(values: &[f64], term: impl Fn(f64) -> f64) -> f64 {
    let mut lanes = [0.0; LANES];
    let (chunks, tail) = values.as_chunks::<LANES>();

    for chunk in chunks {
        for (lane, &value) in lanes.iter_mut().zip(chunk) {
            *lane += term(value);
        }
    }

    tail.iter().map(|&value| term(value)).sum::<f64>() + lanes.iter().sum::<f64>()
}
