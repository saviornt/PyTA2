//! OBV, A/D and CMF invariants that must hold for any valid input.

use proptest::prelude::*;
use pyta_core::Series;
use pyta_volume::{ad, cmf, obv};

/// Close and whole-number volume columns of 1 to 300 rows, some closes
/// repeating the previous one and some volumes zero.
fn close_and_volume() -> impl Strategy<Value = (Vec<f64>, Vec<f64>)> {
    let row = (
        prop_oneof![4 => 1.0..1.0e4_f64, 1 => Just(f64::NAN)],
        prop_oneof![4 => 0_u32..1_000_000_000, 1 => Just(0)],
    );
    prop::collection::vec(row, 1..300).prop_map(|rows| {
        let mut close: Vec<f64> = Vec::with_capacity(rows.len());
        for &(price, _) in &rows {
            // NaN means "repeat the previous close".
            let price = match close.last() {
                Some(&previous) if price.is_nan() => previous,
                _ if price.is_nan() => 100.0,
                _ => price,
            };
            close.push(price);
        }
        let volume = rows.iter().map(|&(_, size)| f64::from(size)).collect();
        (close, volume)
    })
}

fn obv_of(close: &[f64], volume: &[f64]) -> Vec<f64> {
    obv(
        &Series::new(close.to_vec()).unwrap(),
        &Series::new(volume.to_vec()).unwrap(),
    )
    .unwrap()
    .into_values()
}

proptest! {
    #[test]
    fn obv_has_no_warm_up_and_steps_by_the_volume((close, volume) in close_and_volume()) {
        let output = obv_of(&close, &volume);

        prop_assert_eq!(output.len(), close.len());
        prop_assert_eq!(output[0], volume[0]);
        for row in 1..close.len() {
            // Whole volumes below 2^53 in total: every step is exact.
            let step = output[row] - output[row - 1];
            let expected = if close[row] > close[row - 1] {
                volume[row]
            } else if close[row] < close[row - 1] {
                -volume[row]
            } else {
                0.0
            };
            prop_assert_eq!(step, expected, "row {}", row);
        }
    }
}

/// High, low, close and volume of 1 to 300 rows: high at or above low,
/// close inside its bar, some one-price bars and some zero volumes.
fn ohlcv() -> impl Strategy<Value = [Vec<f64>; 4]> {
    let row = (
        -1.0e6..1.0e6_f64,
        prop_oneof![4 => 0.0..1.0e3_f64, 1 => Just(0.0)],
        0.0..=1.0_f64,
        prop_oneof![4 => 0.0..1.0e9_f64, 1 => Just(0.0)],
    );
    prop::collection::vec(row, 1..300).prop_map(|rows| {
        let low: Vec<f64> = rows.iter().map(|row| row.0).collect();
        let high = rows.iter().map(|row| row.0 + row.1).collect();
        let close = rows.iter().map(|row| row.0 + row.1 * row.2).collect();
        let volume = rows.iter().map(|row| row.3).collect();
        [high, low, close, volume]
    })
}

fn ad_of(columns: &[Vec<f64>; 4]) -> Vec<f64> {
    let [high, low, close, volume] = columns.clone().map(|values| Series::new(values).unwrap());
    ad(&high, &low, &close, &volume).unwrap().into_values()
}

/// TA-Lib 0.8.3's `TA_AD` loop written out, with its `tmp > 0.0` branch.
fn reference_ad([high, low, close, volume]: &[Vec<f64>; 4]) -> Vec<f64> {
    let mut total = 0.0_f64;
    (0..close.len())
        .map(|row| {
            let tmp = high[row] - low[row];
            if tmp > 0.0 {
                total += (close[row] - low[row] - (high[row] - close[row])) / tmp * volume[row];
            }
            total
        })
        .collect()
}

proptest! {
    #[test]
    fn ad_matches_talibs_loop_bit_for_bit(columns in ohlcv()) {
        let actual = ad_of(&columns);
        let expected = reference_ad(&columns);

        prop_assert_eq!(actual.len(), columns[0].len());
        for (index, (a, e)) in actual.iter().zip(&expected).enumerate() {
            prop_assert!(a.to_bits() == e.to_bits(), "index {}: {:e} != {:e}", index, a, e);
        }
    }

    #[test]
    fn ad_steps_are_at_most_the_volume(columns in ohlcv()) {
        let output = ad_of(&columns);
        let volume = &columns[3];

        // With the close inside its bar the multiplier is within [-1, 1];
        // the step also carries the running total's rounding.
        prop_assert!(output[0].abs() <= volume[0] * (1.0 + 1e-12));
        for row in 1..output.len() {
            let step = (output[row] - output[row - 1]).abs();
            let slack = 1e-9 * (output[row].abs() + output[row - 1].abs());
            prop_assert!(step <= volume[row] * (1.0 + 1e-12) + slack, "row {}", row);
        }
    }
}

/// A long random walk of high, low, close and volume (1,000 to 4,000 rows,
/// the close inside its bar, runs of zero volume and volumes spanning nine
/// orders of magnitude) and a period from 1 to 200.
fn long_walk_and_period() -> impl Strategy<Value = ([Vec<f64>; 4], usize)> {
    let row = (
        -1.0..1.0_f64,
        0.0..5.0_f64,
        0.0..=1.0_f64,
        prop_oneof![6 => 0.0..9.0_f64, 1 => Just(f64::NEG_INFINITY)],
    );
    (prop::collection::vec(row, 1_000..4_000), 1..=200_usize).prop_map(|(rows, period)| {
        let mut price = 1_000.0;
        let (mut high, mut low, mut close, mut volume) = (vec![], vec![], vec![], vec![]);
        for (step, range, at, magnitude) in rows {
            price += step;
            low.push(price);
            high.push(price + range);
            close.push(price + range * at);
            // A run of zero volume where the magnitude is -inf, else 10^m.
            volume.push(if magnitude.is_finite() {
                10.0_f64.powf(magnitude)
            } else {
                0.0
            });
        }
        // Make some windows empty: a zero run of `period` rows in the middle.
        let start = high.len() / 2;
        for value in &mut volume[start..(start + period).min(high.len())] {
            *value = 0.0;
        }
        ([high, low, close, volume], period)
    })
}

fn cmf_of(columns: &[Vec<f64>; 4], period: usize) -> Vec<f64> {
    let [high, low, close, volume] = columns.clone().map(|values| Series::new(values).unwrap());
    cmf(&high, &low, &close, &volume, period)
        .unwrap()
        .into_values()
}

/// CMF from fresh sums over every window (no running sums).
fn direct_cmf([high, low, close, volume]: &[Vec<f64>; 4], period: usize) -> Vec<f64> {
    let flow: Vec<f64> = (0..close.len())
        .map(|row| {
            let range = high[row] - low[row];
            let multiplier = if range > 0.0 {
                (close[row] - low[row] - (high[row] - close[row])) / range
            } else {
                0.0
            };
            multiplier * volume[row]
        })
        .collect();
    let mut output = vec![f64::NAN; close.len()];
    for end in period..=close.len() {
        let total: f64 = volume[end - period..end].iter().sum();
        if volume[end - period..end].iter().any(|value| *value != 0.0) {
            output[end - 1] = flow[end - period..end].iter().sum::<f64>() / total;
        }
    }
    output
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(48))]

    #[test]
    fn cmf_matches_fresh_window_sums_on_long_walks((columns, period) in long_walk_and_period()) {
        let actual = cmf_of(&columns, period);
        let expected = direct_cmf(&columns, period);

        prop_assert_eq!(actual.len(), columns[0].len());
        prop_assert!(actual[..period - 1].iter().all(|value| value.is_nan()));
        for (index, (a, e)) in actual.iter().zip(&expected).enumerate() {
            prop_assert_eq!(a.is_nan(), e.is_nan(), "index {}: {} vs {}", index, a, e);
            if !e.is_nan() {
                // CMF is within [-1, 1]; both sides round each window sum.
                prop_assert!((a - e).abs() <= 1e-12, "index {}: {:e} != {:e}", index, a, e);
                prop_assert!(a.abs() <= 1.0 + 1e-12, "index {}: {}", index, a);
            }
        }
    }
}
