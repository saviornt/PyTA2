//! Stochastic kernel: formula, outputs, warm-ups, parameters and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_momentum::stoch;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

/// `stoch_k` and `stoch_d`.
fn lines_of([high, low, close]: [&[f64]; 3], k: usize, k_smooth: usize, d: usize) -> [Vec<f64>; 2] {
    let outputs = stoch(&series(high), &series(low), &series(close), k, k_smooth, d)
        .unwrap()
        .into_outputs();
    outputs.try_into().expect("two outputs")
}

fn assert_close(actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len());
    for (row, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan()) || (a - e).abs() <= 1e-12 * e.abs().max(1.0),
            "row {row}: {a} vs {e}"
        );
    }
}

const NAN: f64 = f64::NAN;

// Seven rows.
const HIGH: [f64; 7] = [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0];
const LOW: [f64; 7] = [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0];
const CLOSE: [f64; 7] = [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0];

#[test]
fn stoch_returns_two_outputs_with_input_length_and_their_own_warm_ups() {
    // k 3, k_smooth 2, d 2: stoch_k from row k + k_smooth - 2 = 3, stoch_d
    // from row k + k_smooth + d - 3 = 4.
    let output = stoch(&series(&HIGH), &series(&LOW), &series(&CLOSE), 3, 2, 2).unwrap();
    assert_eq!(output.output_count(), 2);

    for (line, first) in output.outputs().iter().zip([3, 4]) {
        assert_eq!(line.len(), 7);
        assert!(line[..first].iter().all(|value| value.is_nan()));
        assert!(line[first..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn stoch_matches_a_hand_calculation() {
    // k 3, raw %K from row 2: 100 * (close - lowest) / (highest - lowest):
    // row 2 (12 - 9) / (13 - 9) = 75, row 3 (11 - 10) / (13 - 10) = 33.3..,
    // row 4 (13 - 10) / (14 - 10) = 75, row 5 (14 - 10) / (15 - 10) = 80,
    // row 6 (13 - 11) / (15 - 11) = 50.
    let third = 100.0 / 3.0;
    let [stoch_k, stoch_d] = lines_of([&HIGH, &LOW, &CLOSE], 3, 2, 2);

    let k_lines = [(75.0 + third) / 2.0, (third + 75.0) / 2.0, 77.5, 65.0];
    assert_close(
        &stoch_k,
        &[
            NAN, NAN, NAN, k_lines[0], k_lines[1], k_lines[2], k_lines[3],
        ],
    );
    assert_close(
        &stoch_d,
        &[
            NAN,
            NAN,
            NAN,
            NAN,
            (k_lines[0] + k_lines[1]) / 2.0,
            (k_lines[1] + k_lines[2]) / 2.0,
            (k_lines[2] + k_lines[3]) / 2.0,
        ],
    );
}

#[test]
fn stoch_with_no_smoothing_is_the_fast_stochastic() {
    // k_smooth 1 gives raw %K itself; d 1 copies it.
    let [stoch_k, stoch_d] = lines_of([&HIGH, &LOW, &CLOSE], 3, 1, 1);

    assert_close(&stoch_k, &[NAN, NAN, 75.0, 100.0 / 3.0, 75.0, 80.0, 50.0]);
    assert_eq!(stoch_k[2..], stoch_d[2..]);
}

#[test]
fn stoch_with_one_row_windows_measures_close_within_the_row() {
    // k 1: (close - low) / (high - low) on each row.
    let [stoch_k, _] = lines_of([&HIGH, &LOW, &CLOSE], 1, 1, 1);
    let expected: Vec<f64> = HIGH
        .iter()
        .zip(&LOW)
        .zip(&CLOSE)
        .map(|((h, l), c)| (c - l) / (h - l) * 100.0)
        .collect();

    assert_eq!(stoch_k, expected);
}

#[test]
fn stoch_is_100_at_the_highest_high_and_0_at_the_lowest_low() {
    let high = [10.0, 11.0, 12.0, 12.0];
    let low = [8.0, 9.0, 10.0, 7.0];
    let close = [9.0, 10.0, 12.0, 7.0];
    let [stoch_k, _] = lines_of([&high, &low, &close], 3, 1, 1);

    assert_eq!(&stoch_k[2..], &[100.0, 0.0]);
}

#[test]
fn stoch_is_zero_on_a_flat_window() {
    // TA-Lib 0.8.3: a zero range gives raw %K 0, and so both averages.
    let level = [105.0; 6];
    let [stoch_k, stoch_d] = lines_of([&level, &level, &level], 3, 2, 2);

    assert!(stoch_k[3..].iter().all(|value| *value == 0.0));
    assert!(stoch_d[4..].iter().all(|value| *value == 0.0));
}

#[test]
fn stoch_treats_a_range_within_rounding_of_its_extremes_as_flat() {
    // A range of 1e-9 against extremes near 1e6 is below
    // `1e-14 * (|highest| + |lowest|)` = 2e-8 (`TA_IS_ZERO_SCALED`): 0, not
    // 50. The same range near 1 is a real range.
    let [stoch_k, _] = lines_of([&[1.0e6 + 1.0e-9], &[1.0e6], &[1.0e6 + 0.5e-9]], 1, 1, 1);
    assert_eq!(stoch_k, [0.0]);

    let [stoch_k, _] = lines_of([&[1.0 + 1.0e-9], &[1.0], &[1.0 + 0.5e-9]], 1, 1, 1);
    assert!((stoch_k[0] - 50.0).abs() < 1e-3, "{}", stoch_k[0]);
}

#[test]
fn stoch_keeps_talib_running_sum_residue_after_a_flat_stretch() {
    // TA-Lib's SMA subtracts the oldest value from a running total, so a
    // flat stretch after non-zero values may leave a rounding residue in
    // %D rather than 0; whatever it is, it matches a plain running total.
    let high = [10.0, 11.0, 10.3, 10.0, 10.0, 10.0, 10.0, 10.0];
    let low = [9.0, 9.7, 9.1, 10.0, 10.0, 10.0, 10.0, 10.0];
    let close = [9.3, 10.9, 9.9, 10.0, 10.0, 10.0, 10.0, 10.0];
    let [stoch_k, stoch_d] = lines_of([&high, &low, &close], 1, 3, 3);

    let raw: Vec<f64> = (0..8)
        .map(|row| {
            let range = high[row] - low[row];
            if range == 0.0 {
                0.0
            } else {
                (close[row] - low[row]) / range * 100.0
            }
        })
        .collect();
    let running = |values: &[f64], period: usize| {
        let mut total: f64 = values[..period - 1].iter().sum();
        let mut means = Vec::new();
        for row in period - 1..values.len() {
            total += values[row];
            means.push(total / period as f64);
            total -= values[row + 1 - period];
        }
        means
    };

    let expected_k = running(&raw, 3);
    assert_eq!(&stoch_k[2..], &expected_k[..]);
    assert_eq!(&stoch_d[4..], &running(&expected_k, 3)[..]);
}

#[test]
fn stoch_rejects_a_zero_parameter_naming_it() {
    for ((k, k_smooth, d), name) in [((0, 2, 2), "k"), ((3, 0, 2), "k_smooth"), ((3, 2, 0), "d")] {
        assert_eq!(
            stoch(
                &series(&HIGH),
                &series(&LOW),
                &series(&CLOSE),
                k,
                k_smooth,
                d
            ),
            Err(PytaError::InvalidParameter {
                name,
                minimum: 1,
                value: 0,
            })
        );
    }
}

#[test]
fn stoch_rejects_columns_of_unequal_length() {
    for [high, low, close] in [
        [&HIGH[..6], &LOW[..], &CLOSE[..]],
        [&HIGH[..], &LOW[..6], &CLOSE[..]],
        [&HIGH[..], &LOW[..], &CLOSE[..6]],
    ] {
        assert_eq!(
            stoch(&series(high), &series(low), &series(close), 3, 2, 2),
            Err(PytaError::LengthMismatch)
        );
    }
}

#[test]
fn stoch_needs_k_plus_k_smooth_plus_d_minus_2_rows() {
    // 8 rows in each case, one more than given.
    for (k, k_smooth, d) in [(6, 2, 2), (3, 5, 2), (3, 2, 5), (8, 1, 1)] {
        assert_eq!(
            stoch(
                &series(&HIGH),
                &series(&LOW),
                &series(&CLOSE),
                k,
                k_smooth,
                d
            ),
            Err(PytaError::InsufficientData {
                required: 8,
                length: 7,
            }),
            "parameters {k}, {k_smooth}, {d}"
        );
    }
}

#[test]
fn stoch_reports_a_huge_parameter_without_overflow() {
    assert_eq!(
        stoch(
            &series(&HIGH),
            &series(&LOW),
            &series(&CLOSE),
            3,
            usize::MAX,
            2
        ),
        Err(PytaError::InsufficientData {
            required: usize::MAX - 2,
            length: 7,
        })
    );
}

#[test]
fn stoch_accepts_minimum_data() {
    // k + k_smooth + d - 2 = 7 rows: both outputs have a value on row 6 only
    // (stoch_d) or from row k + k_smooth - 2 (stoch_k).
    for (k, k_smooth, d) in [(5, 2, 2), (2, 5, 2), (2, 2, 5), (7, 1, 1)] {
        let [stoch_k, stoch_d] = lines_of([&HIGH, &LOW, &CLOSE], k, k_smooth, d);

        assert!(
            stoch_k[k + k_smooth - 2..]
                .iter()
                .all(|value| value.is_finite())
        );
        assert!(stoch_d[..6].iter().all(|value| value.is_nan()));
        assert!(stoch_d[6].is_finite());
    }
}

#[test]
fn stoch_is_finite_at_the_magnitude_limit() {
    let high = [MAX_ABS_INPUT; 4];
    let low = [-MAX_ABS_INPUT; 4];
    let close = [0.0, MAX_ABS_INPUT, -MAX_ABS_INPUT, 0.0];
    let [stoch_k, stoch_d] = lines_of([&high, &low, &close], 2, 2, 1);

    assert!(stoch_k[2..].iter().all(|value| value.is_finite()));
    assert!(stoch_d[2..].iter().all(|value| value.is_finite()));
    assert_eq!(&stoch_k[2..], &[50.0, 25.0]);
}
