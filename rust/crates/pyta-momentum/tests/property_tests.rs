//! RSI, CCI, Stochastic, Williams %R, ROC, MFI and TRIX invariants that must hold for any valid input.

use proptest::prelude::*;
use pyta_core::Series;
use pyta_momentum::rsi;

/// Prices of ordinary size, mixed with tiny ones and exact repeats, which
/// make the average loss negligible next to the average gain (or zero).
fn price() -> impl Strategy<Value = f64> {
    prop_oneof![
        4 => -1.0e6..1.0e6_f64,
        1 => -1.0e-290..1.0e-290_f64,
        1 => Just(0.0),
    ]
}

/// A series of 2 to 300 prices and a period that leaves at least one RSI value.
fn series_and_period() -> impl Strategy<Value = (Vec<f64>, usize)> {
    prop::collection::vec(price(), 2..300).prop_flat_map(|values| {
        let length = values.len();
        (Just(values), 1..length)
    })
}

proptest! {
    #[test]
    fn output_length_and_warm_up_are_exact((values, period) in series_and_period()) {
        let output = rsi(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..period].iter().all(|value| value.is_nan()));
        prop_assert!(output[period..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn values_lie_between_zero_and_one_hundred((values, period) in series_and_period()) {
        let output = rsi(&Series::new(values).unwrap(), period).unwrap();

        for value in &output.values()[period..] {
            prop_assert!((0.0..=100.0).contains(value), "{} outside [0, 100]", value);
        }
    }

    #[test]
    fn constant_input_gives_zero(
        value in -1.0e6..1.0e6_f64,
        length in 2_usize..300,
        period_seed in 0_usize..300,
    ) {
        let period = period_seed % (length - 1) + 1;
        let output = rsi(&Series::new(vec![value; length]).unwrap(), period).unwrap();

        prop_assert!(output.values()[period..].iter().all(|value| *value == 0.0));
    }

    #[test]
    fn rsi_is_invariant_under_a_positive_scale(
        (values, period) in series_and_period(),
        scale in 1.0e-3..1.0e3_f64,
    ) {
        let scaled: Vec<f64> = values.iter().map(|value| value * scale).collect();

        let plain = rsi(&Series::new(values).unwrap(), period).unwrap();
        let scaled = rsi(&Series::new(scaled).unwrap(), period).unwrap();

        for (a, b) in plain.values().iter().zip(scaled.values()).skip(period) {
            prop_assert!((a - b).abs() <= 1.0e-6, "{} vs {}", a, b);
        }
    }
}

/// High, low and close columns of 1 to 300 rows (high at or above low) and
/// a period that leaves at least one CCI value.
fn columns_and_period() -> impl Strategy<Value = ([Vec<f64>; 3], usize)> {
    prop::collection::vec((-1.0e6..1.0e6_f64, 0.0..1.0e3_f64, 0.0..=1.0_f64), 1..300).prop_flat_map(
        |rows| {
            let length = rows.len();
            let low: Vec<f64> = rows.iter().map(|(low, _, _)| *low).collect();
            let high: Vec<f64> = rows.iter().map(|(low, range, _)| low + range).collect();
            let close = rows
                .iter()
                .map(|(low, range, at)| low + range * at)
                .collect();
            (Just([high, low, close]), 1..=length)
        },
    )
}

fn cci_of(columns: &[Vec<f64>; 3], period: usize) -> Vec<f64> {
    let [high, low, close] = columns.clone().map(|values| Series::new(values).unwrap());

    pyta_momentum::cci(&high, &low, &close, period)
        .unwrap()
        .into_values()
}

proptest! {
    #[test]
    fn cci_output_length_and_warm_up_are_exact((columns, period) in columns_and_period()) {
        let output = cci_of(&columns, period);

        prop_assert_eq!(output.len(), columns[0].len());
        prop_assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        prop_assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn cci_is_bounded_by_the_window_length((columns, period) in columns_and_period()) {
        // The deviations from the mean sum to zero, so the others sum to
        // -(TP - mean) and the absolute deviations to at least 2|TP - mean|:
        // the mean deviation is at least 2|TP - mean| / period, and
        // |CCI| <= period / (2 * 0.015).
        let bound = period as f64 / 0.03 * (1.0 + 1e-9);

        for value in &cci_of(&columns, period)[period - 1..] {
            prop_assert!(value.abs() <= bound, "{} outside ±{}", value, bound);
        }
    }

    #[test]
    fn cci_is_invariant_under_a_shift_and_a_positive_scale(
        (columns, period) in columns_and_period(),
        scale in 1.0e-2..1.0e2_f64,
        shift in -1.0e3..1.0e3_f64,
    ) {
        let moved = columns.clone().map(|values| values.iter().map(|v| v * scale + shift).collect());

        for (a, b) in cci_of(&columns, period).iter().zip(cci_of(&moved, period)).skip(period - 1) {
            // A window that is flat within rounding may read 0 on one side only.
            prop_assert!((a - b).abs() <= 1.0e-4 * (1.0 + a.abs()) || *a == 0.0 || b == 0.0, "{} vs {}", a, b);
        }
    }
}

/// RSI's smoothing written out as a plain loop, the form it had before it
/// moved onto `pyta_core::kernels::WilderAverage`: the indicator must match
/// it bit for bit.
fn reference_rsi(prices: &[f64], period: usize) -> Vec<f64> {
    let index_of = |gain: f64, loss: f64| {
        if gain == 0.0 {
            0.0
        } else if loss == 0.0 {
            100.0
        } else {
            100.0 * (gain / (gain + loss))
        }
    };

    let mut output = vec![f64::NAN; prices.len()];
    let (mut gain_sum, mut loss_sum) = (0.0, 0.0);
    for index in 1..=period {
        let change = prices[index] - prices[index - 1];
        if change > 0.0 {
            gain_sum += change;
        } else {
            loss_sum -= change;
        }
    }

    let period_f = period as f64;
    let prior_weight = (period - 1) as f64 / period_f;
    let current_weight = 1.0 / period_f;
    let mut average_gain = gain_sum / period_f;
    let mut average_loss = loss_sum / period_f;
    output[period] = index_of(average_gain, average_loss);

    for index in period + 1..prices.len() {
        let change = prices[index] - prices[index - 1];
        average_gain = average_gain * prior_weight + change.max(0.0) * current_weight;
        average_loss = average_loss * prior_weight + (-change).max(0.0) * current_weight;
        output[index] = index_of(average_gain, average_loss);
    }
    output
}

/// High, low and close columns of 1 to 300 rows (high at or above low,
/// close between them, some rows flat) and Stochastic parameters that fit.
fn columns_and_stoch_parameters() -> impl Strategy<Value = ([Vec<f64>; 3], [usize; 3])> {
    let row = (
        -1.0e6..1.0e6_f64,
        prop_oneof![Just(0.0), 0.0..1.0e3_f64],
        0.0..=1.0_f64,
    );
    prop::collection::vec(row, 1..300).prop_flat_map(|rows| {
        let length = rows.len();
        let low: Vec<f64> = rows.iter().map(|(low, _, _)| *low).collect();
        let high: Vec<f64> = rows.iter().map(|(low, range, _)| low + range).collect();
        let close: Vec<f64> = rows
            .iter()
            .map(|(low, range, at)| low + range * at)
            .collect();
        // k + k_smooth + d - 2 <= length.
        (1..=length).prop_flat_map(move |k| {
            let columns = [high.clone(), low.clone(), close.clone()];
            (1..=length + 1 - k).prop_flat_map(move |k_smooth| {
                let columns = columns.clone();
                (1..=length + 2 - k - k_smooth)
                    .prop_map(move |d| (columns.clone(), [k, k_smooth, d]))
            })
        })
    })
}

fn stoch_of(columns: &[Vec<f64>; 3], [k, k_smooth, d]: [usize; 3]) -> [Vec<f64>; 2] {
    let [high, low, close] = columns.clone().map(|values| Series::new(values).unwrap());
    let outputs = pyta_momentum::stoch(&high, &low, &close, k, k_smooth, d)
        .unwrap()
        .into_outputs();
    outputs.try_into().expect("two outputs")
}

/// Stochastic written out plainly: each window scanned for its extremes,
/// TA-Lib's guard and ratio, and TA-Lib's running-sum SMA.
fn reference_stoch(
    [high, low, close]: &[Vec<f64>; 3],
    [k, k_smooth, d]: [usize; 3],
) -> [Vec<f64>; 2] {
    let length = close.len();
    let sma = |values: &[f64], period: usize, start: usize| {
        let mut output = vec![f64::NAN; length];
        let mut total = 0.0;
        for value in &values[start..start + period - 1] {
            total += value;
        }
        for row in start + period - 1..length {
            total += values[row];
            output[row] = total / period as f64;
            total -= values[row + 1 - period];
        }
        output
    };

    let mut raw = vec![f64::NAN; length];
    for row in k - 1..length {
        let window = row + 1 - k..=row;
        let highest = high[window.clone()]
            .iter()
            .copied()
            .fold(f64::MIN, f64::max);
        let lowest = low[window].iter().copied().fold(f64::MAX, f64::min);
        let range = highest - lowest;
        raw[row] = if range.abs() <= 1.0e-14 * (highest.abs() + lowest.abs()) {
            0.0
        } else {
            (close[row] - lowest) / range * 100.0
        };
    }
    let stoch_k = sma(&raw, k_smooth, k - 1);
    let stoch_d = sma(&stoch_k, d, k + k_smooth - 2);
    [stoch_k, stoch_d]
}

proptest! {
    #[test]
    fn stoch_outputs_and_warm_ups_are_exact((columns, parameters) in columns_and_stoch_parameters()) {
        let [k, k_smooth, d] = parameters;
        let starts = [k + k_smooth - 2, k + k_smooth + d - 3];

        for (line, start) in stoch_of(&columns, parameters).iter().zip(starts) {
            prop_assert_eq!(line.len(), columns[0].len());
            prop_assert!(line[..start].iter().all(|value| value.is_nan()));
            prop_assert!(line[start..].iter().all(|value| value.is_finite()));
        }
    }

    #[test]
    fn stoch_stays_between_0_and_100((columns, parameters) in columns_and_stoch_parameters()) {
        // With the close inside each row's range, raw %K is in [0, 100]; the
        // running sums may round a hair past either end.
        let slack = 1.0e-9;

        for line in stoch_of(&columns, parameters) {
            for value in line.iter().filter(|value| !value.is_nan()) {
                prop_assert!(*value >= -slack && *value <= 100.0 + slack, "{} outside [0, 100]", value);
            }
        }
    }

    #[test]
    fn stoch_matches_its_plain_loop_bit_for_bit((columns, parameters) in columns_and_stoch_parameters()) {
        let actual = stoch_of(&columns, parameters);
        let expected = reference_stoch(&columns, parameters);

        for (output, (line, want)) in actual.iter().zip(&expected).enumerate() {
            for (index, (a, e)) in line.iter().zip(want).enumerate() {
                prop_assert!(
                    (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
                    "output {}, index {}: {:e} != {:e}", output, index, a, e
                );
            }
        }
    }
}

/// High, low and close columns of 2 to 300 rows (high at or above low, some
/// rows flat, close mostly inside its row but sometimes outside, which
/// Williams %R clamps) and a period from 2 to the row count.
fn columns_and_willr_period() -> impl Strategy<Value = ([Vec<f64>; 3], usize)> {
    let row = (
        -1.0e6..1.0e6_f64,
        prop_oneof![Just(0.0), 0.0..1.0e3_f64],
        prop_oneof![4 => 0.0..=1.0_f64, 1 => -0.5..1.5_f64],
    );
    prop::collection::vec(row, 2..300).prop_flat_map(|rows| {
        let length = rows.len();
        let low: Vec<f64> = rows.iter().map(|(low, _, _)| *low).collect();
        let high: Vec<f64> = rows.iter().map(|(low, range, _)| low + range).collect();
        let close: Vec<f64> = rows
            .iter()
            .map(|(low, range, at)| low + range * at)
            .collect();
        (Just([high, low, close]), 2..=length)
    })
}

fn willr_of(columns: &[Vec<f64>; 3], period: usize) -> Vec<f64> {
    let [high, low, close] = columns.clone().map(|values| Series::new(values).unwrap());
    pyta_momentum::willr(&high, &low, &close, period)
        .unwrap()
        .values()
        .to_vec()
}

/// Williams %R written out plainly: each window scanned for its extremes,
/// then TA-Lib's guard, ratio and clamp.
#[expect(
    clippy::manual_clamp,
    reason = "TA-Lib's own branches, to check the kernel's `clamp` against"
)]
fn reference_willr([high, low, close]: &[Vec<f64>; 3], period: usize) -> Vec<f64> {
    let mut output = vec![f64::NAN; close.len()];
    for row in period - 1..close.len() {
        let window = row + 1 - period..=row;
        let highest = high[window.clone()]
            .iter()
            .copied()
            .fold(f64::MIN, f64::max);
        let lowest = low[window].iter().copied().fold(f64::MAX, f64::min);
        let range = highest - lowest;
        output[row] = if range.abs() <= 1.0e-14 * (highest.abs() + lowest.abs()) {
            0.0
        } else {
            let value = (highest - close[row]) / range * -100.0;
            if value > 0.0 {
                0.0
            } else if value < -100.0 {
                -100.0
            } else {
                value
            }
        };
    }
    output
}

proptest! {
    #[test]
    fn willr_output_length_and_warm_up_are_exact((columns, period) in columns_and_willr_period()) {
        let output = willr_of(&columns, period);

        prop_assert_eq!(output.len(), columns[0].len());
        prop_assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        prop_assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn willr_stays_between_minus_100_and_0((columns, period) in columns_and_willr_period()) {
        for value in &willr_of(&columns, period)[period - 1..] {
            prop_assert!((-100.0..=0.0).contains(value), "{} outside [-100, 0]", value);
        }
    }

    #[test]
    fn willr_matches_its_plain_loop_bit_for_bit((columns, period) in columns_and_willr_period()) {
        let actual = willr_of(&columns, period);
        let expected = reference_willr(&columns, period);

        for (index, (a, e)) in actual.iter().zip(&expected).enumerate() {
            prop_assert!(
                (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
                "index {}: {:e} != {:e}", index, a, e
            );
        }
    }
}

proptest! {
    #[test]
    fn rsi_matches_its_plain_loop_bit_for_bit((values, period) in series_and_period()) {
        let output = rsi(&Series::new(values.clone()).unwrap(), period).unwrap();
        let expected = reference_rsi(&values, period);

        for (index, (a, e)) in output.values().iter().zip(&expected).enumerate() {
            prop_assert!(
                (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
                "index {}: {:e} != {:e}", index, a, e
            );
        }
    }
}

proptest! {
    #[test]
    fn roc_output_length_and_warm_up_are_exact((values, period) in series_and_period()) {
        // `price()` includes tiny values, so a ratio may overflow to an
        // infinity as TA-Lib's does; only the warm-up is NaN.
        let output = pyta_momentum::roc(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..period].iter().all(|value| value.is_nan()));
        prop_assert!(output[period..].iter().all(|value| !value.is_nan()));
    }

    #[test]
    fn roc_of_a_positive_series_is_above_minus_100(
        values in prop::collection::vec(1.0e-3..1.0e6_f64, 2..300),
        period_seed in 0_usize..300,
    ) {
        let period = period_seed % (values.len() - 1) + 1;
        let output = pyta_momentum::roc(&Series::new(values).unwrap(), period).unwrap();

        for value in &output.values()[period..] {
            prop_assert!(value.is_finite() && *value > -100.0, "{}", value);
        }
    }
}

/// High, low, close and volume of 3 to 300 rows (high at or above low, close
/// inside its row, some rows repeating the previous one so the typical price
/// is unchanged, some volumes zero) and a period from 2 to rows - 1.
fn columns_and_mfi_period() -> impl Strategy<Value = ([Vec<f64>; 4], usize)> {
    let row = (
        prop_oneof![4 => 1.0..1.0e4_f64, 1 => Just(f64::NAN)],
        0.0..10.0_f64,
        0.0..=1.0_f64,
        prop_oneof![4 => 0.0..1.0e9_f64, 1 => Just(0.0)],
    );
    prop::collection::vec(row, 3..300).prop_flat_map(|rows| {
        let length = rows.len();
        let (mut high, mut low, mut close, mut volume) = (vec![], vec![], vec![], vec![]);
        for (index, &(base, range, at, size)) in rows.iter().enumerate() {
            // NaN means "repeat the previous row's prices".
            if base.is_nan() && index > 0 {
                high.push(high[index - 1]);
                low.push(low[index - 1]);
                close.push(close[index - 1]);
            } else {
                let base = if base.is_nan() { 100.0 } else { base };
                high.push(base + range);
                low.push(base);
                close.push(base + range * at);
            }
            volume.push(size);
        }
        (Just([high, low, close, volume]), 2..length)
    })
}

fn mfi_of(columns: &[Vec<f64>; 4], period: usize) -> Vec<f64> {
    let [high, low, close, volume] = columns.clone().map(|values| Series::new(values).unwrap());
    pyta_momentum::mfi(&high, &low, &close, &volume, period)
        .unwrap()
        .values()
        .to_vec()
}

/// TA-Lib 0.8.3's `TA_MFI` loop written out: ring buffers of the flows,
/// subtract the oldest before adding the newest, the null-run reset and the
/// clamped ratio, in TA-Lib's own branches (to check the kernel's `clamp`
/// against).
fn reference_mfi([high, low, close, volume]: &[Vec<f64>; 4], period: usize) -> Vec<f64> {
    let mut output = vec![f64::NAN; close.len()];
    let (mut positive_ring, mut negative_ring) = (vec![0.0; period], vec![0.0; period]);
    let (mut positive, mut negative) = (0.0_f64, 0.0_f64);
    let mut previous = (high[0] + low[0] + close[0]) / 3.0;
    let (mut null_run, mut slot) = (0, 0);

    for today in 1..close.len() {
        if today > period {
            positive -= positive_ring[slot];
            negative -= negative_ring[slot];
        }
        let typical = (high[today] + low[today] + close[today]) / 3.0;
        let change = typical - previous;
        let scale = typical.abs() + previous.abs();
        previous = typical;
        let money_flow = if change.abs() <= 1.0e-14 * scale {
            0.0
        } else {
            typical * volume[today]
        };
        positive_ring[slot] = if change < 0.0 { 0.0 } else { money_flow };
        negative_ring[slot] = if change < 0.0 { money_flow } else { 0.0 };
        positive += positive_ring[slot];
        negative += negative_ring[slot];
        null_run = if money_flow == 0.0 { null_run + 1 } else { 0 };
        if null_run >= period {
            null_run = period;
            positive = 0.0;
            negative = 0.0;
        }
        if today >= period {
            let total = positive + negative;
            let clamped = if positive < 0.0 {
                0.0
            } else if positive > total {
                total
            } else {
                positive
            };
            output[today] = if total <= 0.0 {
                0.0
            } else {
                100.0 * (clamped / total)
            };
        }
        slot = (slot + 1) % period;
    }
    output
}

proptest! {
    #[test]
    fn mfi_output_length_and_warm_up_are_exact((columns, period) in columns_and_mfi_period()) {
        let output = mfi_of(&columns, period);

        prop_assert_eq!(output.len(), columns[0].len());
        prop_assert!(output[..period].iter().all(|value| value.is_nan()));
        prop_assert!(output[period..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn mfi_stays_between_0_and_100((columns, period) in columns_and_mfi_period()) {
        for value in &mfi_of(&columns, period)[period..] {
            prop_assert!((0.0..=100.0).contains(value), "{} outside [0, 100]", value);
        }
    }

    #[test]
    fn mfi_matches_talibs_loop_bit_for_bit((columns, period) in columns_and_mfi_period()) {
        let actual = mfi_of(&columns, period);
        let expected = reference_mfi(&columns, period);

        for (index, (a, e)) in actual.iter().zip(&expected).enumerate() {
            prop_assert!(
                (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
                "index {}: {:e} != {:e}", index, a, e
            );
        }
    }
}

/// A series of 2 to 300 prices (some flat stretches) and a TRIX period that
/// leaves at least one value (`3 * period - 1` rows).
fn series_and_trix_period() -> impl Strategy<Value = (Vec<f64>, usize)> {
    let value = prop_oneof![4 => 1.0..1.0e4_f64, 1 => Just(100.0), 1 => -1.0e6..1.0e6_f64];
    prop::collection::vec(value, 2..300).prop_flat_map(|values| {
        let longest = (values.len() + 1) / 3;
        (Just(values), 1..=longest)
    })
}

/// TRIX from the shared kernels: three cascaded `kernels::ema` passes and
/// `kernels::rate_of_change` of the third.
fn cascaded_trix(values: &[f64], period: usize) -> Vec<f64> {
    use pyta_core::kernels::{ema, rate_of_change};

    let offset = period - 1;
    let ema1 = ema(values, period);
    let ema2 = ema(&ema1[offset..], period);
    let ema3 = ema(&ema2[offset..], period);

    let mut output = vec![f64::NAN; 3 * offset];
    output.extend(rate_of_change(&ema3[offset..], 1));
    output
}

proptest! {
    #[test]
    fn trix_output_length_and_warm_up_are_exact((values, period) in series_and_trix_period()) {
        let output = pyta_momentum::trix(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();
        let first = 3 * (period - 1) + 1;

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..first].iter().all(|value| value.is_nan()));
        // A ratio to a tiny non-zero EMA may overflow, as TA-Lib's does.
        prop_assert!(output[first..].iter().all(|value| !value.is_nan()));
    }

    #[test]
    fn trix_fused_pass_matches_the_cascaded_kernels_bit_for_bit(
        (values, period) in series_and_trix_period()
    ) {
        let output = pyta_momentum::trix(&Series::new(values.clone()).unwrap(), period).unwrap();
        let expected = cascaded_trix(&values, period);

        for (index, (a, e)) in output.values().iter().zip(&expected).enumerate() {
            prop_assert!(
                (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
                "index {}: {:e} != {:e}", index, a, e
            );
        }
    }
}
