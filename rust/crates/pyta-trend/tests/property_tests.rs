//! SMA, EMA and MACD invariants that must hold for any valid input.

use proptest::prelude::*;
use pyta_core::Series;
use pyta_trend::{ema, macd, sma};

/// A series of 1 to 300 prices and a period that fits it.
fn series_and_period() -> impl Strategy<Value = (Vec<f64>, usize)> {
    prop::collection::vec(-1.0e6..1.0e6_f64, 1..300).prop_flat_map(|values| {
        let length = values.len();
        (Just(values), 1..=length)
    })
}

proptest! {
    #[test]
    fn output_length_and_warm_up_are_exact((values, period) in series_and_period()) {
        let output = sma(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        prop_assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn each_value_lies_within_its_window((values, period) in series_and_period()) {
        let output = sma(&Series::new(values.clone()).unwrap(), period).unwrap();

        for (index, average) in output.values().iter().enumerate().skip(period - 1) {
            let window = &values[index + 1 - period..=index];
            let low = window.iter().copied().fold(f64::INFINITY, f64::min);
            let high = window.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            // Rounding in the running sum may step just outside the range.
            let slack = 1.0e-9 * high.abs().max(low.abs()).max(1.0);

            prop_assert!(
                *average >= low - slack && *average <= high + slack,
                "index {}: {} outside [{}, {}]", index, average, low, high
            );
        }
    }

    #[test]
    fn constant_input_gives_a_constant_average(
        value in -1.0e6..1.0e6_f64,
        length in 1_usize..300,
        period_seed in 0_usize..300,
    ) {
        let period = period_seed % length + 1;
        let output = sma(&Series::new(vec![value; length]).unwrap(), period).unwrap();

        for average in &output.values()[period - 1..] {
            prop_assert!((average - value).abs() <= 1.0e-12 * value.abs().max(1.0));
        }
    }
}

/// A series and MACD parameters that fit it; `fast` and `slow` come in
/// either order, since the kernel swaps them.
fn series_and_macd_parameters() -> impl Strategy<Value = (Vec<f64>, usize, usize, usize)> {
    (2_usize..40, 2_usize..40, 1_usize..20).prop_flat_map(|(fast, slow, signal)| {
        let required = fast.max(slow) + signal - 1;
        (
            prop::collection::vec(-1.0e6..1.0e6_f64, required..required + 200),
            Just(fast),
            Just(slow),
            Just(signal),
        )
    })
}

proptest! {
    #[test]
    fn ema_output_length_and_warm_up_are_exact((values, period) in series_and_period()) {
        let output = ema(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        prop_assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn ema_stays_within_the_range_of_its_input((values, period) in series_and_period()) {
        let output = ema(&Series::new(values.clone()).unwrap(), period).unwrap();
        let low = values.iter().copied().fold(f64::INFINITY, f64::min);
        let high = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let slack = 1.0e-9 * high.abs().max(low.abs()).max(1.0);

        for average in &output.values()[period - 1..] {
            prop_assert!(*average >= low - slack && *average <= high + slack);
        }
    }

    #[test]
    fn macd_outputs_have_the_input_length_and_their_own_warm_up(
        (values, fast, slow, signal) in series_and_macd_parameters()
    ) {
        let output = macd(&Series::new(values.clone()).unwrap(), fast, slow, signal).unwrap();
        let [line, signal_line, hist] = output.outputs() else {
            panic!("expected three outputs");
        };
        let line_start = fast.max(slow) - 1;
        let signal_start = line_start + signal - 1;

        for series in [line, signal_line, hist] {
            prop_assert_eq!(series.len(), values.len());
        }
        prop_assert!(line[..line_start].iter().all(|value| value.is_nan()));
        prop_assert!(line[line_start..].iter().all(|value| value.is_finite()));
        for series in [signal_line, hist] {
            prop_assert!(series[..signal_start].iter().all(|value| value.is_nan()));
            prop_assert!(series[signal_start..].iter().all(|value| value.is_finite()));
        }
    }

    #[test]
    fn macd_histogram_is_exactly_macd_minus_signal(
        (values, fast, slow, signal) in series_and_macd_parameters()
    ) {
        let output = macd(&Series::new(values).unwrap(), fast, slow, signal).unwrap();
        let [line, signal_line, hist] = output.outputs() else {
            panic!("expected three outputs");
        };

        for index in 0..line.len() {
            if signal_line[index].is_nan() {
                prop_assert!(hist[index].is_nan());
            } else {
                prop_assert_eq!(hist[index], line[index] - signal_line[index]);
            }
        }
    }

    #[test]
    fn macd_of_constant_input_is_zero(
        value in -1.0e6..1.0e6_f64,
        fast in 2_usize..30,
        slow in 2_usize..30,
        signal in 1_usize..15,
        extra in 0_usize..50,
    ) {
        let length = fast.max(slow) + signal - 1 + extra;
        let output = macd(&Series::new(vec![value; length]).unwrap(), fast, slow, signal).unwrap();
        // The SMA seeds of a constant may differ from it by rounding.
        let tolerance = 1.0e-9 * value.abs().max(1.0);

        for series in output.outputs() {
            for result in series.iter().filter(|result| !result.is_nan()) {
                prop_assert!(result.abs() <= tolerance, "{} is not 0", result);
            }
        }
    }
}
