//! Williams %R kernel: formula, warm-up, parameters and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_momentum::willr;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn willr_of([high, low, close]: [&[f64]; 3], period: usize) -> Vec<f64> {
    willr(&series(high), &series(low), &series(close), period)
        .unwrap()
        .values()
        .to_vec()
}

// Seven rows.
const HIGH: [f64; 7] = [11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 14.0];
const LOW: [f64; 7] = [9.0, 10.0, 11.0, 10.0, 11.0, 12.0, 12.0];
const CLOSE: [f64; 7] = [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0];

#[test]
fn willr_has_input_length_and_period_minus_1_warm_up() {
    for period in 2..=7 {
        let output = willr_of([&HIGH, &LOW, &CLOSE], period);

        assert_eq!(output.len(), 7);
        assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn willr_matches_a_hand_calculation() {
    // Period 3, from row 2: (highest - close) / (highest - lowest) * -100:
    // row 2 (13 - 12) / (13 - 9) = -25, row 3 (13 - 11) / (13 - 10) =
    // -66.6.., row 4 (14 - 13) / (14 - 10) = -25, row 5 (15 - 14) /
    // (15 - 10) = -20, row 6 (15 - 13) / (15 - 11) = -50.
    let output = willr_of([&HIGH, &LOW, &CLOSE], 3);

    assert_eq!(
        output[2..],
        [
            1.0 / 4.0 * -100.0,
            2.0 / 3.0 * -100.0,
            1.0 / 4.0 * -100.0,
            1.0 / 5.0 * -100.0,
            2.0 / 4.0 * -100.0,
        ]
    );
    assert!(output[..2].iter().all(|value| value.is_nan()));
}

#[test]
fn willr_is_0_at_the_highest_high_and_minus_100_at_the_lowest_low() {
    let high = [10.0, 11.0, 12.0, 12.0];
    let low = [8.0, 9.0, 10.0, 7.0];
    let close = [9.0, 10.0, 12.0, 7.0];
    let output = willr_of([&high, &low, &close], 3);

    assert_eq!(&output[2..], &[0.0, -100.0]);
    // TA-Lib writes `0 * -100`, a negative zero, and so does PyTA.
    assert!(output[2].is_sign_negative());
}

#[test]
fn willr_is_zero_on_a_flat_window() {
    // TA-Lib 0.8.3: a zero range gives 0.
    let level = [105.0; 6];
    let output = willr_of([&level, &level, &level], 3);

    assert!(output[..2].iter().all(|value| value.is_nan()));
    assert!(output[2..].iter().all(|value| *value == 0.0));
    assert!(output[2..].iter().all(|value| value.is_sign_positive()));
}

#[test]
fn willr_treats_a_range_within_rounding_of_its_extremes_as_flat() {
    // A range of 1e-9 against extremes near 1e6 is below
    // `1e-14 * (|highest| + |lowest|)` = 2e-8 (`TA_IS_ZERO_SCALED`): 0, not
    // -50. The same range near 1 is a real range.
    let high = [1.0e6 + 1.0e-9, 1.0e6 + 1.0e-9];
    let low = [1.0e6, 1.0e6];
    let close = [1.0e6 + 0.5e-9, 1.0e6 + 0.5e-9];
    assert_eq!(willr_of([&high, &low, &close], 2)[1], 0.0);

    let high = [1.0 + 1.0e-9, 1.0 + 1.0e-9];
    let low = [1.0, 1.0];
    let close = [1.0 + 0.5e-9, 1.0 + 0.5e-9];
    let output = willr_of([&high, &low, &close], 2);
    assert!((output[1] + 50.0).abs() < 1e-3, "{}", output[1]);
}

#[test]
fn willr_clamps_a_close_outside_its_window() {
    // Nothing checks the close against high and low, so TA-Lib clamps:
    // above the highest high gives 0, below the lowest low -100.
    let high = [10.0, 11.0, 11.0];
    let low = [9.0, 9.5, 9.5];
    let close = [9.5, 12.0, 8.0];
    let output = willr_of([&high, &low, &close], 2);

    assert_eq!(&output[1..], &[0.0, -100.0]);
    assert!(output[1].is_sign_positive());
}

#[test]
fn willr_rejects_a_period_below_2() {
    for period in [0, 1] {
        assert_eq!(
            willr(&series(&HIGH), &series(&LOW), &series(&CLOSE), period),
            Err(PytaError::InvalidParameter {
                name: "period",
                minimum: 2,
                value: period,
            })
        );
    }
}

#[test]
fn willr_rejects_columns_of_different_lengths() {
    let short = &CLOSE[..6];
    for [high, low, close] in [
        [short, &LOW, &CLOSE],
        [&HIGH, short, &CLOSE],
        [&HIGH, &LOW, short],
    ] {
        assert_eq!(
            willr(&series(high), &series(low), &series(close), 3),
            Err(PytaError::LengthMismatch)
        );
    }
}

#[test]
fn willr_needs_period_rows() {
    assert_eq!(
        willr(&series(&HIGH), &series(&LOW), &series(&CLOSE), 8),
        Err(PytaError::PeriodExceedsLength {
            period: 8,
            length: 7,
        })
    );
    assert_eq!(
        willr(&series(&HIGH), &series(&LOW), &series(&CLOSE), usize::MAX),
        Err(PytaError::PeriodExceedsLength {
            period: usize::MAX,
            length: 7,
        })
    );
}

#[test]
fn willr_accepts_minimum_data() {
    // `period` rows give one value, on the last row: (14 - 13) / (15 - 9).
    let output = willr_of([&HIGH, &LOW, &CLOSE], 7);

    assert!(output[..6].iter().all(|value| value.is_nan()));
    assert_eq!(output[6], 2.0 / 6.0 * -100.0);
}

#[test]
fn willr_is_finite_at_the_magnitude_limit() {
    let high = [MAX_ABS_INPUT; 3];
    let low = [-MAX_ABS_INPUT; 3];
    let close = [0.0, MAX_ABS_INPUT, -MAX_ABS_INPUT];
    let output = willr_of([&high, &low, &close], 2);

    assert_eq!(&output[1..], &[0.0, -100.0]);
    let output = willr_of([&high, &low, &[0.0; 3]], 2);
    assert_eq!(output[1], -50.0);
}
