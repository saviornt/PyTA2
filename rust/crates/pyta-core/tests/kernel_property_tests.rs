//! Kernel invariants that must hold for any valid input, checked against
//! plain reference implementations.

use proptest::prelude::*;
use pyta_core::kernels::{
    WilderAverage, WilderSum, ema, ema_into, for_each_window_max, for_each_window_min,
    rolling_mean, rolling_mean_std, true_range,
};

/// A series of 1 to 300 values of ordinary size and a period that fits it.
fn series_and_period() -> impl Strategy<Value = (Vec<f64>, usize)> {
    prop::collection::vec(-1.0e6..1.0e6_f64, 1..300).prop_flat_map(|values| {
        let length = values.len();
        (Just(values), 1..=length)
    })
}

/// Like [`series_and_period`], with values drawn from a few levels so that
/// windows often hold ties.
fn tied_series_and_period() -> impl Strategy<Value = (Vec<f64>, usize)> {
    prop::collection::vec((0..4_u8).prop_map(f64::from), 1..200).prop_flat_map(|values| {
        let length = values.len();
        (Just(values), 1..=length)
    })
}

/// TA-Lib's EMA as one plain loop, the form the kernel replaced in
/// `pyta-trend`: the kernel must match it bit for bit.
fn reference_ema(values: &[f64], period: usize) -> Vec<f64> {
    let k = 2.0 / (period + 1) as f64;
    let mut output = vec![f64::NAN; values.len()];
    let mut previous = values[..period].iter().sum::<f64>() / period as f64;
    output[period - 1] = previous;
    for index in period..values.len() {
        previous = (values[index] - previous) * k + previous;
        output[index] = previous;
    }
    output
}

/// The window extreme by rescanning, ties to the most recent row.
fn rescan(values: &[f64], period: usize, better_or_equal: fn(f64, f64) -> bool) -> Vec<usize> {
    (period - 1..values.len())
        .map(|row| {
            let mut best = row + 1 - period;
            for index in best + 1..=row {
                if better_or_equal(values[index], values[best]) {
                    best = index;
                }
            }
            best
        })
        .collect()
}

fn same_bits(left: &[f64], right: &[f64]) -> bool {
    left.len() == right.len()
        && left
            .iter()
            .zip(right)
            .all(|(l, r)| (l.is_nan() && r.is_nan()) || l.to_bits() == r.to_bits())
}

proptest! {
    #[test]
    fn ema_matches_the_plain_loop_bit_for_bit((values, period) in series_and_period()) {
        prop_assume!(period >= 2);
        prop_assert!(same_bits(&ema(&values, period), &reference_ema(&values, period)));
    }

    #[test]
    fn a_cascade_through_a_slice_equals_a_late_seeded_pass(
        (values, period) in series_and_period()
    ) {
        // EMA of an EMA: the second pass over `first[p-1..]`, shifted back,
        // equals `ema_into` over the whole first EMA seeded `p - 1` later.
        prop_assume!(period >= 2 && 2 * period - 1 <= values.len());
        let first = ema(&values, period);
        let mut shifted = vec![f64::NAN; period - 1];
        shifted.extend(ema(&first[period - 1..], period));

        let mut seeded = vec![f64::NAN; values.len()];
        ema_into(&first, period, 2 * period - 2, &mut seeded);
        prop_assert!(same_bits(&shifted, &seeded));
    }

    #[test]
    fn deque_extremes_match_a_rescan((values, period) in tied_series_and_period()) {
        let mut maxima = Vec::new();
        for_each_window_max(&values, period, |_, index| maxima.push(index));
        prop_assert_eq!(maxima, rescan(&values, period, |a, b| a >= b));

        let mut minima = Vec::new();
        for_each_window_min(&values, period, |_, index| minima.push(index));
        prop_assert_eq!(minima, rescan(&values, period, |a, b| a <= b));
    }

    #[test]
    fn deque_extremes_match_a_rescan_on_continuous_values(
        (values, period) in series_and_period()
    ) {
        let mut maxima = Vec::new();
        for_each_window_max(&values, period, |_, index| maxima.push(index));
        prop_assert_eq!(maxima, rescan(&values, period, |a, b| a >= b));
    }

    #[test]
    fn rolling_mean_and_std_match_a_two_pass_reference(
        (values, period) in series_and_period()
    ) {
        let means = rolling_mean(&values, period);
        let (means_too, deviations) = rolling_mean_std(&values, period);
        prop_assert!(same_bits(&means, &means_too));
        prop_assert!(means[..period - 1].iter().all(|value| value.is_nan()));
        prop_assert!(deviations[..period - 1].iter().all(|value| value.is_nan()));

        for (row, window) in values.windows(period).enumerate() {
            let count = period as f64;
            let mean = window.iter().sum::<f64>() / count;
            let std = (window.iter().map(|x| (x - mean) * (x - mean)).sum::<f64>() / count).sqrt();
            let magnitude = window.iter().fold(0.0_f64, |m, x| m.max(x.abs()));
            let (actual_mean, actual_std) = (means[row + period - 1], deviations[row + period - 1]);

            prop_assert!((actual_mean - mean).abs() <= 1e-12 * magnitude.max(1e-300));
            prop_assert!(
                (actual_std - std).abs() <= 1e-12 * std + 1e-15 * magnitude,
                "row {}: {} != {}", row, actual_std, std
            );
        }
    }

    #[test]
    fn true_range_covers_the_bar_and_the_gap(
        rows in prop::collection::vec((-1.0e6..1.0e6_f64, 0.0..1.0e3_f64, 0.0..1.0_f64), 1..200)
    ) {
        let low: Vec<f64> = rows.iter().map(|row| row.0).collect();
        let high: Vec<f64> = rows.iter().map(|row| row.0 + row.1).collect();
        let close: Vec<f64> = rows.iter().map(|row| row.0 + row.1 * row.2).collect();
        let output = true_range(&high, &low, &close);

        prop_assert_eq!(output.len(), close.len());
        prop_assert!(output[0].is_nan());
        for index in 1..close.len() {
            let range = output[index];
            prop_assert!(range >= high[index] - low[index]);
            prop_assert!(range >= (high[index] - close[index - 1]).abs());
            prop_assert!(range >= (low[index] - close[index - 1]).abs());
            // The range spans the bar and the previous close, no more.
            let top = high[index].max(close[index - 1]);
            let bottom = low[index].min(close[index - 1]);
            prop_assert_eq!(range, top - bottom);
        }
    }

    #[test]
    fn wilder_sum_tracks_n_times_the_average(
        values in prop::collection::vec(0.0..1.0e6_f64, 1..300),
        period in 1..50_usize,
    ) {
        let mut average = WilderAverage::new(period, values[0]);
        let mut sum = WilderSum::new(period, values[0] * period as f64);
        for &value in &values {
            let (a, s) = (average.update(value), sum.update(value));
            prop_assert!((s - a * period as f64).abs() <= 1e-9 * s.abs().max(1.0));
            prop_assert!(a >= 0.0);
        }
    }
}
