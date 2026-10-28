//! RSI invariants that must hold for any valid input.

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
