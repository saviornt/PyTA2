//! CCI kernel: formula, warm-up, edge cases and magnitude limits.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_momentum::cci;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

/// CCI with high = low = close, so the typical price is `close`.
fn cci_of_close(close: &[f64], period: usize) -> Vec<f64> {
    let close = series(close);

    cci(&close, &close, &close, period).unwrap().into_values()
}

#[test]
fn cci_preserves_input_length_and_warmup_alignment() {
    let result = cci_of_close(&[1.0, 2.0, 3.0, 4.0, 5.0], 3);

    assert_eq!(result.len(), 5);
    assert!(result[..2].iter().all(|value| value.is_nan()));
    assert!(result[2..].iter().all(|value| value.is_finite()));
}

#[test]
fn cci_matches_a_hand_calculation() {
    // Window [1, 2, 3]: mean 2, mean deviation 2/3, CCI = (3 - 2) / (0.015 * 2/3) = 100.
    // Window [2, 3, 7]: mean 4, mean deviation 2, CCI = (7 - 4) / (0.015 * 2) = 100.
    let result = cci_of_close(&[1.0, 2.0, 3.0, 7.0], 3);

    assert!((result[2] - 100.0).abs() < 1e-9, "got {}", result[2]);
    assert!((result[3] - 100.0).abs() < 1e-9, "got {}", result[3]);
}

#[test]
fn cci_uses_the_typical_price_of_high_low_and_close() {
    let high = series(&[3.0, 6.0, 9.0]);
    let low = series(&[0.0, 0.0, 0.0]);
    let close = series(&[0.0, 0.0, 0.0]);

    // Typical prices 1, 2, 3, as in the hand calculation above.
    let result = cci(&high, &low, &close, 3).unwrap();

    assert!((result.values()[2] - 100.0).abs() < 1e-9);
}

#[test]
fn cci_rejects_zero_period() {
    let close = series(&[1.0, 2.0]);

    assert_eq!(
        cci(&close, &close, &close, 0),
        Err(PytaError::InvalidPeriod)
    );
}

#[test]
fn cci_rejects_insufficient_data() {
    let close = series(&[1.0, 2.0]);

    assert_eq!(
        cci(&close, &close, &close, 3),
        Err(PytaError::InsufficientData {
            required: 3,
            length: 2,
        })
    );
}

#[test]
fn cci_accepts_minimum_data() {
    let result = cci_of_close(&[1.0, 2.0, 3.0], 3);

    assert!(result[..2].iter().all(|value| value.is_nan()));
    assert!((result[2] - 100.0).abs() < 1e-9);
}

#[test]
fn cci_rejects_columns_of_different_lengths() {
    let short = series(&[1.0, 2.0]);
    let long = series(&[1.0, 2.0, 3.0]);

    assert_eq!(cci(&long, &short, &long, 2), Err(PytaError::LengthMismatch));
    assert_eq!(cci(&long, &long, &short, 2), Err(PytaError::LengthMismatch));
}

#[test]
fn cci_is_zero_for_a_flat_window() {
    let result = cci_of_close(&[5.0, 5.0, 5.0, 5.0], 2);

    assert_eq!(&result[1..], &[0.0, 0.0, 0.0]);
}

#[test]
fn cci_is_zero_when_the_latest_price_equals_the_mean() {
    // Window [1, 3, 2]: mean 2, the latest typical price.
    let result = cci_of_close(&[1.0, 3.0, 2.0], 3);

    assert_eq!(result[2], 0.0);
}

#[test]
fn cci_treats_a_deviation_within_rounding_of_the_mean_as_zero() {
    // A difference of one part in 1e16 of the mean is rounding, not movement.
    let base = 1.0e6;
    let result = cci_of_close(&[base, base, base * (1.0 + 1e-16)], 3);

    assert_eq!(result[2], 0.0);
}

#[test]
fn cci_with_period_one_is_zero_throughout() {
    let result = cci_of_close(&[1.0, 5.0, -3.0], 1);

    assert_eq!(result, vec![0.0, 0.0, 0.0]);
}

#[test]
fn cci_is_finite_at_the_magnitude_limit() {
    let result = cci_of_close(
        &[MAX_ABS_INPUT, -MAX_ABS_INPUT, MAX_ABS_INPUT, -MAX_ABS_INPUT],
        2,
    );

    assert!(result[1..].iter().all(|value| value.is_finite()));
}

/// CCI of `close` as high, low and close, with each window summed afresh,
/// and how far a correct result may be from it.
///
/// The window is summed relative to its first price, which is exact for
/// nearby prices. Even so, the mean is a float, rounded to about `1e-16` of
/// the window's size; that rounding, divided by `0.015` times the mean
/// deviation, bounds how closely any method can agree.
fn fresh_sum_cci(close: &[f64], period: usize) -> Vec<(f64, f64)> {
    let typical: Vec<f64> = close.iter().map(|x| (x + x + x) / 3.0).collect();

    typical
        .windows(period)
        .map(|window| {
            let pivot = window[0];
            let mean = pivot + window.iter().map(|x| x - pivot).sum::<f64>() / period as f64;
            let deviation = window.iter().map(|x| (x - mean).abs()).sum::<f64>() / period as f64;
            let size = window.iter().fold(0.0_f64, |size, x| size.max(x.abs()));
            let cci = (window[period - 1] - mean) / (0.015 * deviation);
            (cci, 1e-12 * size / (0.015 * deviation) + 1e-9 * cci.abs())
        })
        .collect()
}

#[test]
fn a_flat_window_after_a_large_price_leaves_is_exactly_zero() {
    // A plain running sum keeps the rounding error of the large prices after
    // they leave the window, and reads it as movement (CCI about -66.7).
    let mut close: Vec<f64> = (0..50).map(|i| 1.0e9 + f64::from(i) * 0.1).collect();
    close.extend([5.0; 30]);

    let result = cci_of_close(&close, 14);

    assert!(
        result[50 + 13..].iter().all(|value| *value == 0.0),
        "{result:?}"
    );
}

#[test]
fn the_running_mean_does_not_drift_over_a_long_series() {
    // Blocks of prices near 1e9 and near 1, so every switch leaves a large
    // rounding error in a plain running sum.
    let close: Vec<f64> = (0..200_000_u32)
        .map(|i| {
            let wave = (f64::from(i) * 0.37).sin();
            if (i / 1_000) % 2 == 0 {
                1.0e9 + 100.0 * wave
            } else {
                1.0 + 0.01 * wave
            }
        })
        .collect();

    for period in [3, 14, 20, 50] {
        let result = cci_of_close(&close, period);
        let expected = fresh_sum_cci(&close, period);

        for (index, (got, (want, tolerance))) in
            result[period - 1..].iter().zip(&expected).enumerate()
        {
            assert!(
                (got - want).abs() <= *tolerance,
                "period {period}, row {}: got {got}, fresh sum gives {want} (±{tolerance})",
                index + period - 1
            );
        }
    }
}
