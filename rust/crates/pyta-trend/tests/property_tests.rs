//! SMA invariants that must hold for any valid input.

use proptest::prelude::*;
use pyta_core::Series;
use pyta_trend::sma;

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
