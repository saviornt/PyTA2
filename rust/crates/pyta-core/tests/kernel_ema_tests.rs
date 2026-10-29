//! The shared EMA kernel: seed, recurrence, period edge cases, cascading.

use pyta_core::kernels::{ema, ema_into, ema_multiplier, ema_step};

fn assert_close(actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len());
    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        if e.is_nan() {
            assert!(a.is_nan(), "index {index}: {a} should be NaN");
        } else {
            assert!(
                (a - e).abs() <= 1e-12 * e.abs().max(1.0),
                "index {index}: {a} != {e}"
            );
        }
    }
}

#[test]
fn ema_is_seeded_with_the_simple_average_then_smoothed() {
    // k = 0.5: seed (1 + 2 + 3) / 3 = 2, then 2 + (4 - 2) / 2 = 3, then 4.
    let output = ema(&[1.0, 2.0, 3.0, 4.0, 5.0], 3);
    assert_close(&output, &[f64::NAN, f64::NAN, 2.0, 3.0, 4.0]);
}

#[test]
fn period_one_is_an_exact_copy() {
    let values = [1.1, 2.7, -3.3, 1e-300];
    let output = ema(&values, 1);
    assert_eq!(output, values);
}

#[test]
fn period_equal_to_the_length_gives_one_value_the_mean() {
    let output = ema(&[2.0, 4.0, 9.0], 3);
    assert_close(&output, &[f64::NAN, f64::NAN, 5.0]);
}

#[test]
fn flat_input_stays_flat() {
    let output = ema(&[7.25; 10], 4);
    assert!(output[..3].iter().all(|value| value.is_nan()));
    assert!(output[3..].iter().all(|&value| value == 7.25));
}

#[test]
fn ema_into_seeds_at_a_later_start_and_leaves_earlier_positions_alone() {
    // Seed at index 3 from (3 + 4) / 2, k = 2/3: 3.5 + (5 - 3.5) * 2/3 = 4.5.
    let mut output = [-1.0; 5];
    ema_into(&[1.0, 2.0, 3.0, 4.0, 5.0], 2, 3, &mut output);
    assert_close(&output, &[-1.0, -1.0, -1.0, 3.5, 4.5]);
}

#[test]
fn a_cascaded_ema_starts_after_the_first_ema_warm_up() {
    // The EMA of [2, 3, 4] (the first EMA's values) with period 3 is their mean.
    let first = ema(&[1.0, 2.0, 3.0, 4.0, 5.0], 3);
    let second = ema(&first[2..], 3);
    assert_close(&second, &[f64::NAN, f64::NAN, 3.0]);
}

#[test]
fn multiplier_and_step_follow_ta_lib() {
    assert_eq!(ema_multiplier(1), 1.0);
    assert_eq!(ema_multiplier(3), 0.5);
    assert_eq!(ema_step(2.0, 4.0, 0.5), 3.0);
    // TA-Lib's order: (value - previous) * k + previous, not previous * (1 - k) + value * k.
    let (previous, value, k) = (0.1, 0.7, ema_multiplier(9));
    assert_eq!(
        ema_step(previous, value, k).to_bits(),
        ((value - previous) * k + previous).to_bits()
    );
}
