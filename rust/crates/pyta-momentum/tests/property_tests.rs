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
