//! ROC kernel: formula, warm-up, period checks and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_momentum::roc;

fn roc_of(values: &[f64], period: usize) -> Vec<f64> {
    roc(&Series::new(values.to_vec()).unwrap(), period)
        .unwrap()
        .values()
        .to_vec()
}

const PRICES: [f64; 6] = [10.0, 11.0, 12.0, 9.0, 12.0, 13.2];

#[test]
fn roc_has_input_length_and_period_warm_up() {
    for period in 1..=5 {
        let output = roc_of(&PRICES, period);

        assert_eq!(output.len(), PRICES.len());
        assert!(output[..period].iter().all(|value| value.is_nan()));
        assert!(output[period..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn roc_matches_a_hand_calculation() {
    // Period 3: 9 against 10 is -10%, 12 against 11 about 9.09%, 13.2
    // against 12 is 10%.
    let output = roc_of(&PRICES, 3);

    assert!(output[..3].iter().all(|value| value.is_nan()));
    let expected = [-10.0, 100.0 / 11.0, 10.0];
    for (got, want) in output[3..].iter().zip(expected) {
        assert!((got - want).abs() < 1e-12, "{got} vs {want}");
    }
}

#[test]
fn roc_is_zero_for_a_zero_base_and_for_flat_input() {
    // An earlier value of exactly 0 gives 0, not an infinity (as TA-Lib).
    let output = roc_of(&[0.0, 5.0, 5.0, 0.0, 5.0], 1);
    assert_eq!(output[1..], [0.0, 0.0, -100.0, 0.0]);

    assert!(
        roc_of(&[105.0; 5], 2)[2..]
            .iter()
            .all(|value| *value == 0.0)
    );
}

#[test]
fn roc_rejects_a_zero_period() {
    assert_eq!(
        roc(&Series::new(PRICES.to_vec()).unwrap(), 0),
        Err(PytaError::InvalidPeriod)
    );
}

#[test]
fn roc_needs_period_plus_1_rows() {
    let series = Series::new(PRICES.to_vec()).unwrap();

    assert_eq!(
        roc(&series, 6),
        Err(PytaError::InsufficientData {
            required: 7,
            length: 6,
        })
    );
    assert_eq!(
        roc(&series, usize::MAX),
        Err(PytaError::InsufficientData {
            required: usize::MAX,
            length: 6,
        })
    );
}

#[test]
fn roc_accepts_minimum_data() {
    let output = roc_of(&[4.0, 5.0], 1);

    assert!(output[0].is_nan());
    assert_eq!(output[1], 25.0);
}

#[test]
fn roc_is_finite_at_the_magnitude_limit() {
    let output = roc_of(&[MAX_ABS_INPUT, -MAX_ABS_INPUT, MAX_ABS_INPUT], 1);
    assert_eq!(output[1..], [-200.0, -200.0]);
}

#[test]
fn roc_is_zero_on_a_tiny_base_where_talib_overflows_to_infinity() {
    // A base within 1e-14 of the current value's size counts as zero, so
    // 1e10 / 1e-300 (an infinity in TA-Lib) and 1 / 1e-300 read 0.
    let output = roc_of(&[1e-300, 1e10, 1e-300, 1.0], 1);
    assert_eq!(output[1], 0.0);
    assert_eq!(output[3], 0.0);
    assert!(output[1..].iter().all(|value| value.is_finite()));
}
