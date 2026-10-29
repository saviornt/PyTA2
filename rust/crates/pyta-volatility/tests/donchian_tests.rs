//! Donchian Channels kernel: formula, outputs, warm-up, parameters and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_volatility::donchian;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

/// Upper, middle and lower channels.
fn channels_of(high: &[f64], low: &[f64], period: usize) -> [Vec<f64>; 3] {
    let outputs = donchian(&series(high), &series(low), period)
        .unwrap()
        .into_outputs();
    outputs.try_into().expect("three outputs")
}

// Windows of 3, current row included:
// rows 0-2: highest 12, lowest 9;  rows 1-3: 14, 9;  rows 2-4: 14, 10;
// rows 3-5: 14, 8;  rows 4-6: 13, 8.
const HIGH: [f64; 7] = [11.0, 12.0, 11.0, 14.0, 13.0, 10.0, 12.0];
const LOW: [f64; 7] = [9.0, 9.0, 10.0, 12.0, 11.0, 8.0, 10.0];

#[test]
fn donchian_returns_three_outputs_with_input_length_and_shared_warm_up() {
    let output = donchian(&series(&HIGH), &series(&LOW), 3).unwrap();

    assert_eq!(output.output_count(), 3);
    for channel in output.outputs() {
        assert_eq!(channel.len(), 7);
        assert!(channel[..2].iter().all(|value| value.is_nan()));
        assert!(channel[2..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn donchian_matches_a_hand_calculation() {
    let [upper, middle, lower] = channels_of(&HIGH, &LOW, 3);

    assert_eq!(&upper[2..], &[12.0, 14.0, 14.0, 14.0, 13.0]);
    assert_eq!(&lower[2..], &[9.0, 9.0, 10.0, 8.0, 8.0]);
    assert_eq!(&middle[2..], &[10.5, 11.5, 12.0, 11.0, 10.5]);
}

#[test]
fn donchian_window_includes_the_current_row() {
    // A new high on the last row is the upper channel on that same row
    // (StockCharts' price channel, which uses the prior rows, would not
    // include it).
    let [upper, _, lower] = channels_of(&[1.0, 2.0, 9.0], &[0.5, 1.5, 0.1], 2);

    assert_eq!(upper[2], 9.0);
    assert_eq!(lower[2], 0.1);
}

#[test]
fn donchian_with_period_one_is_high_and_low() {
    let [upper, middle, lower] = channels_of(&HIGH, &LOW, 1);

    assert_eq!(upper, HIGH);
    assert_eq!(lower, LOW);
    for row in 0..7 {
        assert_eq!(middle[row], (HIGH[row] + LOW[row]) / 2.0);
    }
}

#[test]
fn donchian_gives_three_equal_channels_when_high_equals_low() {
    let level = [105.0; 6];
    let [upper, middle, lower] = channels_of(&level, &level, 4);

    for row in 3..6 {
        assert_eq!((upper[row], middle[row], lower[row]), (105.0, 105.0, 105.0));
    }
}

#[test]
fn donchian_rejects_zero_period() {
    assert_eq!(
        donchian(&series(&HIGH), &series(&LOW), 0),
        Err(PytaError::InvalidPeriod)
    );
}

#[test]
fn donchian_rejects_columns_of_unequal_length() {
    assert_eq!(
        donchian(&series(&HIGH), &series(&LOW[..6]), 2),
        Err(PytaError::LengthMismatch)
    );
}

#[test]
fn donchian_rejects_a_period_longer_than_the_series() {
    assert_eq!(
        donchian(&series(&[2.0, 3.0, 4.0]), &series(&[1.0, 2.0, 3.0]), 4),
        Err(PytaError::PeriodExceedsLength {
            period: 4,
            length: 3,
        })
    );
}

#[test]
fn donchian_accepts_minimum_data() {
    let [upper, middle, lower] = channels_of(&[3.0, 5.0], &[1.0, 2.0], 2);

    assert!(upper[0].is_nan() && middle[0].is_nan() && lower[0].is_nan());
    assert_eq!((upper[1], middle[1], lower[1]), (5.0, 3.0, 1.0));
}

#[test]
fn donchian_is_finite_at_the_magnitude_limit() {
    let high = [MAX_ABS_INPUT, MAX_ABS_INPUT, MAX_ABS_INPUT];
    let low = [-MAX_ABS_INPUT, MAX_ABS_INPUT, MAX_ABS_INPUT];
    let [upper, middle, lower] = channels_of(&high, &low, 2);

    assert_eq!(&upper[1..], &[MAX_ABS_INPUT, MAX_ABS_INPUT]);
    assert_eq!(&middle[1..], &[0.0, MAX_ABS_INPUT]);
    assert_eq!(&lower[1..], &[-MAX_ABS_INPUT, MAX_ABS_INPUT]);
}
