//! Rolling mean and rolling population standard deviation.

use pyta_core::kernels::{rolling_mean, rolling_mean_into, rolling_mean_std, rolling_std};

#[test]
fn rolling_mean_of_a_ramp() {
    let output = rolling_mean(&[1.0, 2.0, 3.0, 4.0, 5.0], 2);
    assert!(output[0].is_nan());
    assert_eq!(output[1..], [1.5, 2.5, 3.5, 4.5]);
}

#[test]
fn rolling_mean_into_writes_one_mean_per_window() {
    let mut means = [0.0; 3];
    rolling_mean_into(&[1.0, 2.0, 3.0, 4.0, 5.0], 3, &mut means);
    assert_eq!(means, [2.0, 3.0, 4.0]);
}

#[test]
fn rolling_mean_period_one_and_period_equal_to_the_length() {
    let values = [1.5, -2.0, 8.25];
    assert_eq!(rolling_mean(&values, 1), values);
    let whole = rolling_mean(&values, 3);
    assert!((whole[2] - 7.75 / 3.0).abs() <= 1e-15);
}

#[test]
fn rolling_mean_does_not_keep_the_error_of_a_large_value_that_left() {
    // A plain running sum keeps 1e15's rounding error after it leaves.
    let output = rolling_mean(&[1e15, 0.1, 0.1, 0.1, 0.1], 2);
    assert_eq!(output[2..], [0.1, 0.1, 0.1]);
}

#[test]
fn population_standard_deviation_of_a_textbook_sample() {
    // Mean 5, squared deviations sum to 32, 32 / 8 = 4.
    let values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];
    let output = rolling_std(&values, 8);
    assert!(output[..7].iter().all(|value| value.is_nan()));
    assert_eq!(output[7], 2.0);
}

#[test]
fn rolling_mean_std_returns_both_with_the_same_warm_up() {
    let (means, deviations) = rolling_mean_std(&[1.0, 3.0, 5.0, 9.0], 2);
    assert!(means[0].is_nan() && deviations[0].is_nan());
    assert_eq!(means[1..], [2.0, 4.0, 7.0]);
    assert_eq!(deviations[1..], [1.0, 1.0, 2.0]);
}

#[test]
fn period_one_has_no_deviation() {
    let output = rolling_std(&[3.0, -1.0, 7.5], 1);
    assert_eq!(output, [0.0, 0.0, 0.0]);
}

#[test]
fn flat_input_has_no_deviation_within_rounding() {
    for value in [0.1, 1e5 + 0.3, -7.77e100] {
        let output = rolling_std(&[value; 12], 3);
        assert!(
            output[2..]
                .iter()
                .all(|deviation| *deviation >= 0.0 && *deviation <= 1e-15 * value.abs()),
            "{value}: {output:?}"
        );
    }
}

#[test]
fn values_at_the_input_limit_do_not_overflow() {
    // Squares of 1e290 overflow; the deviations are scaled first.
    let output = rolling_std(&[1e290, -1e290, 1e290], 2);
    assert_eq!(output[1..], [1e290, 1e290]);
}

#[test]
fn tiny_values_do_not_underflow_to_zero() {
    // Squares of 1e-200 underflow; the deviations are scaled first.
    let output = rolling_std(&[1e-200, 3e-200], 2);
    assert!(
        (output[1] - 1e-200).abs() <= 1e-15 * 1e-200,
        "{}",
        output[1]
    );
}

#[test]
fn large_offset_with_a_small_spread_stays_accurate() {
    // 1e5 + 1e-3 * noise: a running sum of squares loses every digit here.
    let values: Vec<f64> = (0..2000)
        .map(|i| 1e5 + 1e-3 * ((i as f64 * 0.731).sin() + (i as f64 * 0.117).cos()))
        .collect();
    let period = 20;
    let output = rolling_std(&values, period);

    for (row, window) in values.windows(period).enumerate() {
        // x - 1e5 is exact here (Sterbenz), so this reference sees the same
        // inputs without the offset.
        let centred: Vec<f64> = window.iter().map(|x| x - 1e5).collect();
        let expected = two_pass_std(&centred);
        let actual = output[row + period - 1];
        assert!(
            (actual - expected).abs() <= 1e-9 * expected,
            "row {row}: {actual} != {expected}"
        );
    }
}

/// The textbook two-pass population standard deviation.
fn two_pass_std(window: &[f64]) -> f64 {
    let count = window.len() as f64;
    let mean = window.iter().sum::<f64>() / count;
    (window.iter().map(|x| (x - mean) * (x - mean)).sum::<f64>() / count).sqrt()
}
