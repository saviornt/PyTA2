//! Wilder's smoothing: the average (RSI, ATR) and the running sum (ADX).

use pyta_core::kernels::{WilderAverage, WilderSum, wilder_into};

fn close(actual: f64, expected: f64) -> bool {
    (actual - expected).abs() <= 1e-12 * expected.abs().max(1.0)
}

#[test]
fn average_weights_the_previous_value_by_n_minus_one_over_n() {
    // 3 * 2/3 + 6 * 1/3 = 4.
    let mut average = WilderAverage::new(3, 3.0);
    assert_eq!(average.value(), 3.0);
    assert!(close(average.update(6.0), 4.0));
    assert!(close(average.value(), 4.0));
}

#[test]
fn average_with_period_one_follows_the_input() {
    let mut average = WilderAverage::new(1, 5.0);
    assert_eq!(average.update(2.5), 2.5);
    assert_eq!(average.update(-7.0), -7.0);
}

#[test]
fn average_of_flat_input_stays_flat() {
    let mut average = WilderAverage::new(14, 3.5);
    for _ in 0..1000 {
        assert!(close(average.update(3.5), 3.5));
    }
}

#[test]
fn sum_subtracts_its_own_average_then_adds_the_value() {
    // 9 - 9/3 + 3 = 9.
    let mut sum = WilderSum::new(3, 9.0);
    assert_eq!(sum.update(3.0), 9.0);
    // 9 - 3 + 0 = 6.
    assert_eq!(sum.update(0.0), 6.0);
    assert_eq!(sum.value(), 6.0);
}

#[test]
fn sum_with_period_one_is_the_latest_value() {
    let mut sum = WilderSum::new(1, 4.0);
    assert_eq!(sum.update(2.0), 2.0);
}

#[test]
fn sum_is_n_times_the_average() {
    let values = [1.0, 4.0, 2.0, 8.0, 5.0, 7.0, 3.0];
    let mut average = WilderAverage::new(4, 2.0);
    let mut sum = WilderSum::new(4, 8.0);
    for value in values {
        assert!(close(sum.update(value), 4.0 * average.update(value)));
    }
}

#[test]
fn wilder_into_seeds_with_the_mean_after_an_undefined_first_value() {
    // Like ATR over true range: index 0 is undefined, the seed at index 3 is
    // (1 + 2 + 3) / 3 = 2, then 2 * 2/3 + 4 / 3 = 8/3.
    let values = [f64::NAN, 1.0, 2.0, 3.0, 4.0];
    let mut output = [f64::NAN; 5];
    wilder_into(&values, 3, 3, &mut output);

    assert!(output[..3].iter().all(|value| value.is_nan()));
    assert_eq!(output[3], 2.0);
    assert!(close(output[4], 8.0 / 3.0));
}

#[test]
fn wilder_into_with_period_equal_to_the_length_gives_the_mean() {
    let mut output = [f64::NAN; 3];
    wilder_into(&[3.0, 6.0, 9.0], 3, 2, &mut output);
    assert_eq!(output[2], 6.0);
}
