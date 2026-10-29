//! RSI, CCI and Stochastic invariants that must hold for any valid input.

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
