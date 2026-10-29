//! ATR, STDDEV, BBANDS and Donchian Channels invariants that must hold for any valid input.

use proptest::prelude::*;
use pyta_core::Series;
use pyta_core::kernels::true_range_at;
use pyta_volatility::{atr, bbands, donchian, stddev};

/// High, low and close columns of 2 to 300 rows (high at or above low,
/// close between them) and a period that leaves at least one ATR value.
fn columns_and_period() -> impl Strategy<Value = ([Vec<f64>; 3], usize)> {
    prop::collection::vec((-1.0e6..1.0e6_f64, 0.0..1.0e3_f64, 0.0..=1.0_f64), 2..300).prop_flat_map(
        |rows| {
            let length = rows.len();
            let low: Vec<f64> = rows.iter().map(|(low, _, _)| *low).collect();
            let high: Vec<f64> = rows.iter().map(|(low, range, _)| low + range).collect();
            let close = rows
                .iter()
                .map(|(low, range, at)| low + range * at)
                .collect();
            (Just([high, low, close]), 1..length)
        },
    )
}

fn atr_of(columns: &[Vec<f64>; 3], period: usize) -> Vec<f64> {
    let [high, low, close] = columns.clone().map(|values| Series::new(values).unwrap());

    atr(&high, &low, &close, period).unwrap().into_values()
}

/// TA-Lib's `TA_ATR` written out: the mean of the first `period` true
/// ranges, then `(previous * (period - 1) + range) / period`.
fn talib_atr([high, low, close]: &[Vec<f64>; 3], period: usize) -> Vec<f64> {
    let ranges: Vec<f64> = (1..close.len())
        .map(|i| true_range_at(high[i], low[i], close[i - 1]))
        .collect();

    let mut output = vec![f64::NAN; close.len()];
    let mut average = ranges[..period].iter().sum::<f64>() / period as f64;
    output[period] = average;
    for (index, range) in ranges.iter().enumerate().skip(period) {
        average = (average * (period - 1) as f64 + range) / period as f64;
        output[index + 1] = average;
    }
    output
}

proptest! {
    #[test]
    fn atr_output_length_and_warm_up_are_exact((columns, period) in columns_and_period()) {
        let output = atr_of(&columns, period);

        prop_assert_eq!(output.len(), columns[0].len());
        prop_assert!(output[..period].iter().all(|value| value.is_nan()));
        prop_assert!(output[period..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn atr_lies_between_zero_and_the_largest_true_range((columns, period) in columns_and_period()) {
        let [high, low, close] = &columns;
        let largest = (1..close.len())
            .map(|i| true_range_at(high[i], low[i], close[i - 1]))
            .fold(0.0_f64, f64::max);
        let bound = largest * (1.0 + 1e-12);

        for value in &atr_of(&columns, period)[period..] {
            prop_assert!((0.0..=bound).contains(value), "{} outside [0, {}]", value, bound);
        }
    }

    #[test]
    fn atr_matches_talibs_form_within_rounding((columns, period) in columns_and_period()) {
        // RSI's form of Wilder's average differs from TA-Lib's in the last
        // bit only; the error does not grow.
        let expected = talib_atr(&columns, period);
        let scale = columns[0].iter().chain(&columns[1]).fold(0.0_f64, |m, v| m.max(v.abs()));

        for (index, (a, e)) in atr_of(&columns, period).iter().zip(&expected).enumerate().skip(period) {
            prop_assert!((a - e).abs() <= 1e-12 * (scale + 1.0), "index {}: {} vs {}", index, a, e);
        }
    }

    #[test]
    fn atr_is_invariant_under_a_shift(
        (columns, period) in columns_and_period(),
        shift in -1.0e3..1.0e3_f64,
    ) {
        let moved = columns.clone().map(|values| values.iter().map(|v| v + shift).collect());
        let scale = columns[0].iter().chain(&columns[1]).fold(0.0_f64, |m, v| m.max(v.abs())) + shift.abs();

        for (a, b) in atr_of(&columns, period).iter().zip(atr_of(&moved, period)).skip(period) {
            prop_assert!((a - b).abs() <= 1e-9 * (scale + 1.0), "{} vs {}", a, b);
        }
    }
}

/// A series of 2 to 300 values and a period from 2 to its length.
fn values_and_period() -> impl Strategy<Value = (Vec<f64>, usize)> {
    prop::collection::vec(-1.0e6..1.0e6_f64, 2..300).prop_flat_map(|values| {
        let length = values.len();
        (Just(values), 2..=length)
    })
}

fn stddev_of(values: &[f64], period: usize, k: f64) -> Vec<f64> {
    stddev(&Series::new(values.to_vec()).unwrap(), period, k)
        .unwrap()
        .into_values()
}

proptest! {
    #[test]
    fn stddev_output_length_and_warm_up_are_exact((values, period) in values_and_period()) {
        let output = stddev_of(&values, period, 1.0);

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        prop_assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn stddev_lies_between_zero_and_half_the_window_range((values, period) in values_and_period()) {
        // A population deviation is at most half the window's range.
        let output = stddev_of(&values, period, 1.0);

        for (window, value) in values.windows(period).zip(&output[period - 1..]) {
            let high = window.iter().copied().fold(f64::MIN, f64::max);
            let low = window.iter().copied().fold(f64::MAX, f64::min);
            let bound = (high - low) / 2.0 * (1.0 + 1e-12);
            prop_assert!((0.0..=bound).contains(value), "{} outside [0, {}]", value, bound);
        }
    }

    #[test]
    fn stddev_scales_exactly_with_k((values, period) in values_and_period(), k in 0.01..100.0_f64) {
        let one = stddev_of(&values, period, 1.0);
        let scaled = stddev_of(&values, period, k);

        for (a, b) in one.iter().zip(&scaled).skip(period - 1) {
            prop_assert_eq!(*b, a * k);
        }
    }

    #[test]
    fn stddev_is_invariant_under_a_shift(
        (values, period) in values_and_period(),
        shift in -1.0e3..1.0e3_f64,
    ) {
        let moved: Vec<f64> = values.iter().map(|v| v + shift).collect();
        let scale = values.iter().fold(0.0_f64, |m, v| m.max(v.abs())) + shift.abs();

        for (a, b) in stddev_of(&values, period, 1.0).iter().zip(stddev_of(&moved, period, 1.0)).skip(period - 1) {
            prop_assert!((a - b).abs() <= 1e-9 * (scale + 1.0), "{} vs {}", a, b);
        }
    }
}

fn bbands_of(values: &[f64], period: usize, k: f64) -> Vec<Vec<f64>> {
    bbands(&Series::new(values.to_vec()).unwrap(), period, k)
        .unwrap()
        .into_outputs()
}

proptest! {
    #[test]
    fn bbands_outputs_have_input_length_and_one_shared_warm_up(
        (values, period) in values_and_period(),
        k in 0.01..10.0_f64,
    ) {
        let bands = bbands_of(&values, period, k);

        prop_assert_eq!(bands.len(), 3);
        for band in &bands {
            prop_assert_eq!(band.len(), values.len());
            prop_assert!(band[..period - 1].iter().all(|value| value.is_nan()));
            prop_assert!(band[period - 1..].iter().all(|value| value.is_finite()));
        }
    }

    #[test]
    fn bbands_are_ordered_and_symmetric_about_the_middle(
        (values, period) in values_and_period(),
        k in 0.01..10.0_f64,
    ) {
        // The middle band is the window's mean, within its range; the bands
        // lie k STDDEVs either side of it.
        let bands = bbands_of(&values, period, k);
        let width = stddev_of(&values, period, k);

        for (offset, window) in values.windows(period).enumerate() {
            let row = offset + period - 1;
            let (upper, middle, lower) = (bands[0][row], bands[1][row], bands[2][row]);
            let high = window.iter().copied().fold(f64::MIN, f64::max);
            let low = window.iter().copied().fold(f64::MAX, f64::min);
            let slack = 1e-9 * (high.abs() + low.abs() + 1.0);

            prop_assert!(lower <= middle && middle <= upper, "{} {} {}", lower, middle, upper);
            prop_assert!(low - slack <= middle && middle <= high + slack);
            prop_assert_eq!(upper, middle + width[row]);
            prop_assert_eq!(lower, middle - width[row]);
        }
    }
}

fn donchian_of(columns: &[Vec<f64>; 3], period: usize) -> Vec<Vec<f64>> {
    let [high, low, _] = columns.clone().map(|values| Series::new(values).unwrap());

    donchian(&high, &low, period).unwrap().into_outputs()
}

proptest! {
    #[test]
    fn donchian_outputs_have_input_length_and_one_shared_warm_up(
        (columns, period) in columns_and_period(),
    ) {
        let channels = donchian_of(&columns, period);

        prop_assert_eq!(channels.len(), 3);
        for channel in &channels {
            prop_assert_eq!(channel.len(), columns[0].len());
            prop_assert!(channel[..period - 1].iter().all(|value| value.is_nan()));
            prop_assert!(channel[period - 1..].iter().all(|value| value.is_finite()));
        }
    }

    #[test]
    fn donchian_is_the_window_extremes_and_their_midpoint(
        (columns, period) in columns_and_period(),
    ) {
        // A rescan of every window, current row included.
        let channels = donchian_of(&columns, period);
        let [high, low, _] = &columns;

        for (offset, (highs, lows)) in high.windows(period).zip(low.windows(period)).enumerate() {
            let row = offset + period - 1;
            let top = highs.iter().copied().fold(f64::MIN, f64::max);
            let bottom = lows.iter().copied().fold(f64::MAX, f64::min);
            let (upper, middle, lower) = (channels[0][row], channels[1][row], channels[2][row]);

            prop_assert_eq!(upper, top);
            prop_assert_eq!(lower, bottom);
            prop_assert_eq!(middle, (top + bottom) / 2.0);
            prop_assert!(lower <= middle && middle <= upper);
        }
    }
}
