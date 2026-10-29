//! Row-wise price kernels: true range, typical price, and the scaled zero test.

use pyta_core::kernels::{
    is_zero_scaled, true_range, true_range_at, typical_price, typical_price_at,
};

#[test]
fn true_range_takes_the_largest_of_the_three_ranges() {
    // Inside the previous close: the bar's own range, 2.
    assert_eq!(true_range_at(10.0, 8.0, 9.0), 2.0);
    // Gap up: high - previous close, 15 - 9 = 6.
    assert_eq!(true_range_at(15.0, 13.0, 9.0), 6.0);
    // Gap down: previous close - low, 9 - 4 = 5.
    assert_eq!(true_range_at(6.0, 4.0, 9.0), 5.0);
    // A flat bar on an unchanged close.
    assert_eq!(true_range_at(5.0, 5.0, 5.0), 0.0);
}

#[test]
fn true_range_is_undefined_on_the_first_row() {
    let output = true_range(&[10.0, 15.0, 6.0], &[8.0, 13.0, 4.0], &[9.0, 14.0, 5.0]);
    assert!(output[0].is_nan());
    // max(2, |15 - 9|, |13 - 9|) = 6; max(2, |6 - 14|, |4 - 14|) = 10.
    assert_eq!(output[1..], [6.0, 10.0]);
}

#[test]
fn true_range_of_one_row_or_none() {
    assert!(true_range(&[1.0], &[0.5], &[0.7])[0].is_nan());
    assert!(true_range(&[], &[], &[]).is_empty());
}

#[test]
fn typical_price_is_the_mean_of_high_low_and_close() {
    assert_eq!(typical_price_at(3.0, 1.0, 2.0), 2.0);
    let (high, low, close) = ([3.0, 0.3], [1.0, 0.1], [2.0, 0.2]);
    let output = typical_price(&high, &low, &close);
    assert_eq!(output[0], 2.0);
    // Added left to right, then divided: the same bits as CCI computed.
    assert_eq!(output[1].to_bits(), ((0.3_f64 + 0.1 + 0.2) / 3.0).to_bits());
}

#[test]
fn zero_test_is_relative_to_the_scale_and_inclusive() {
    assert!(is_zero_scaled(1e-14, 1.0));
    assert!(is_zero_scaled(-1e-14, 1.0));
    assert!(!is_zero_scaled(2e-14, 1.0));
    // A rounding error at 1e5 is zero there, but not at 1.
    assert!(is_zero_scaled(1e-10, 1e5));
    assert!(!is_zero_scaled(1e-10, 1.0));
    // A zero scale accepts only zero.
    assert!(is_zero_scaled(0.0, 0.0));
    assert!(!is_zero_scaled(f64::MIN_POSITIVE, 0.0));
}
