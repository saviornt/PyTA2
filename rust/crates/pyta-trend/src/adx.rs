use pyta_core::kernels::{WilderSum, is_zero, true_range_at};
use pyta_core::{IndicatorOutput, PytaError, PytaResult, Series};

/// The smallest `period` ADX accepts (TA-Lib's lower bound).
const MIN_PERIOD: usize = 2;

/// Calculates Wilder's Average Directional Index (ADX) with its two
/// directional indicators, +DI and -DI, as TA-Lib 0.8.3's `TA_ADX`,
/// `TA_PLUS_DI` and `TA_MINUS_DI`, in one pass.
///
/// From row 1, +DM is `high - previous high` when that is positive and
/// larger than `previous low - low`, else 0; -DM is the mirror. With the
/// true range (`pyta_core::kernels::true_range_at`), each is summed over
/// rows `1..period` and then carried by Wilder's smoothed sum
/// (`pyta_core::kernels::WilderSum`) from row `period`.
/// `+DI = 100 * +DM sum / TR sum`, `-DI` likewise, and
/// `DX = 100 * |+DI - -DI| / (+DI + -DI)`. The first ADX, at row
/// `2 * period - 1`, is the mean of the `period` DX values from row
/// `period`; each later one is `ADX - (ADX - DX) / period`, with `1 / period`
/// precomputed as TA-Lib does.
///
/// Returns three outputs, in order: ADX, +DI, -DI. Each has the input's
/// length; +DI and -DI start at row `period`, ADX at row `2 * period - 1`,
/// and the positions before are `NaN` (warm-up). At least `2 * period`
/// values are required.
///
/// Zero guards are TA-Lib's: when the true-range sum is not above 0 (only
/// a series flat from its start), both DIs are 0 and no DX is taken, so the
/// first ADX's mean counts it as 0 and a later ADX keeps its value; a DI sum
/// inside TA-Lib's fixed band `(-1e-14, 1e-14)` (`TA_IS_ZERO`,
/// `pyta_core::kernels::is_zero`) also takes no DX. On a flat stretch after
/// movement both sums shrink by the same factor, so the DIs hold their
/// values and ADX keeps moving towards their DX.
///
/// The columns are not checked against each other (for example high
/// below low); the Python layer does that before calling.
///
/// # Errors
///
/// Returns `InvalidParameter` when `period` is below 2.
/// Returns `LengthMismatch` when the columns differ in length.
/// Returns `InsufficientData` when the input has fewer than `2 * period`
/// values.
pub fn adx(
    high: &Series,
    low: &Series,
    close: &Series,
    period: usize,
) -> PytaResult<IndicatorOutput> {
    if period < MIN_PERIOD {
        return Err(PytaError::InvalidParameter {
            name: "period",
            minimum: MIN_PERIOD,
            value: period,
        });
    }

    let (high, low, close) = (high.values(), low.values(), close.values());
    let length = close.len();

    if high.len() != length || low.len() != length {
        return Err(PytaError::LengthMismatch);
    }

    // Saturates so a huge period from a direct `_native` call is reported,
    // not overflowed; the public API caps periods far below this.
    let required = period.saturating_mul(2);

    if length < required {
        return Err(PytaError::InsufficientData { required, length });
    }

    let mut adx = vec![f64::NAN; length];
    let mut plus_di = vec![f64::NAN; length];
    let mut minus_di = vec![f64::NAN; length];

    let row = |index: usize| Row {
        high: high[index],
        low: low[index],
        previous_high: high[index - 1],
        previous_low: low[index - 1],
        previous_close: close[index - 1],
    };

    // Seeds: plain sums over rows `1..period`.
    let (mut plus_seed, mut minus_seed, mut range_seed) = (0.0, 0.0, 0.0);
    for index in 1..period {
        let row = row(index);
        let (plus, minus) = row.directional_movement();
        plus_seed += plus;
        minus_seed += minus;
        range_seed += row.true_range();
    }

    let mut sums = Sums {
        plus: WilderSum::new(period, plus_seed),
        minus: WilderSum::new(period, minus_seed),
        range: WilderSum::new(period, range_seed),
    };

    // The first ADX is the mean of the DX values of rows
    // `period..=first`.
    let first = 2 * period - 1;
    let mut dx_sum = 0.0;
    for index in period..=first {
        let (plus, minus, dx) = sums.update(row(index));
        plus_di[index] = plus;
        minus_di[index] = minus;
        if let Some(dx) = dx {
            dx_sum += dx;
        }
    }
    let mut average = dx_sum / period as f64;
    adx[first] = average;

    let inverse_period = 1.0 / period as f64;
    for index in first + 1..length {
        let (plus, minus, dx) = sums.update(row(index));
        plus_di[index] = plus;
        minus_di[index] = minus;
        if let Some(dx) = dx {
            average -= (average - dx) * inverse_period;
        }
        adx[index] = average;
    }

    IndicatorOutput::with_outputs(vec![adx, plus_di, minus_di])
}

/// One row and the previous row's values that ADX reads.
#[derive(Clone, Copy)]
struct Row {
    high: f64,
    low: f64,
    previous_high: f64,
    previous_low: f64,
    previous_close: f64,
}

impl Row {
    /// +DM and -DM: the larger of the two moves when it is positive, the
    /// other 0 (TA-Lib's `TA_KEEP_IF_GT` selections; a tie gives both 0).
    #[inline]
    fn directional_movement(self) -> (f64, f64) {
        let up = self.high - self.previous_high;
        let down = self.previous_low - self.low;
        let plus = if up > 0.0 && up - down > 0.0 { up } else { 0.0 };
        let minus = if down > 0.0 && down - up > 0.0 {
            down
        } else {
            0.0
        };
        (plus, minus)
    }

    #[inline]
    fn true_range(self) -> f64 {
        true_range_at(self.high, self.low, self.previous_close)
    }
}

/// Wilder's smoothed sums of +DM, -DM and the true range.
struct Sums {
    plus: WilderSum,
    minus: WilderSum,
    range: WilderSum,
}

impl Sums {
    /// Adds `row` and returns +DI, -DI and the DX, if TA-Lib takes one.
    #[inline]
    fn update(&mut self, row: Row) -> (f64, f64, Option<f64>) {
        let (plus, minus) = row.directional_movement();
        let plus = self.plus.update(plus);
        let minus = self.minus.update(minus);
        let range = self.range.update(row.true_range());

        // TA-Lib tests the true-range sum exactly, not with `TA_IS_ZERO`.
        if range > 0.0 {
            let plus = 100.0 * (plus / range);
            let minus = 100.0 * (minus / range);
            let total = minus + plus;
            let dx = (!is_zero(total)).then(|| 100.0 * ((minus - plus).abs() / total));
            (plus, minus, dx)
        } else {
            (0.0, 0.0, None)
        }
    }
}
