//! TRIX kernel: formula, warm-up, parameters and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::kernels::{ema, rate_of_change};
use pyta_core::{PytaError, Series};
use pyta_momentum::trix;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn trix_of(values: &[f64], period: usize) -> Vec<f64> {
    trix(&series(values), period).unwrap().values().to_vec()
}

/// TRIX built from the shared kernels: three cascaded EMAs, then the
/// one-row rate of change of the third.
fn cascaded(values: &[f64], period: usize) -> Vec<f64> {
    let offset = period - 1;
    let ema1 = ema(values, period);
    let ema2 = ema(&ema1[offset..], period);
    let ema3 = ema(&ema2[offset..], period);
    let roc = rate_of_change(&ema3[offset..], 1);

    let mut output = vec![f64::NAN; 3 * offset];
    output.extend(roc);
    output
}

// Twelve values.
const VALUES: [f64; 12] = [
    10.0, 11.0, 12.5, 12.0, 13.0, 14.5, 14.0, 13.5, 15.0, 16.0, 15.5, 17.0,
];

#[test]
fn trix_has_input_length_and_three_ema_warm_ups_plus_one() {
    for period in 1..=4 {
        let output = trix_of(&VALUES, period);
        let first = 3 * (period - 1) + 1;

        assert_eq!(output.len(), 12);
        assert!(output[..first].iter().all(|value| value.is_nan()));
        assert!(output[first..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn trix_is_bit_for_bit_three_ema_passes_and_a_rate_of_change() {
    for period in 1..=4 {
        let actual = trix_of(&VALUES, period);
        let expected = cascaded(&VALUES, period);

        for (a, e) in actual.iter().zip(&expected) {
            assert!((a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits());
        }
    }
}

#[test]
fn trix_matches_a_hand_calculation() {
    // Period 2 (k = 2/3) on 1, 4, 7, 4: EMA1 2.5, 5.5, 4.5; EMA2 4, 4.333..;
    // EMA3 4.1666.. at row 3 only, so period 2 needs five rows: add 7.
    // EMA1 6.1666.., EMA2 5.5555.., EMA3 (5.5555.. - 4.1666..) * 2/3 +
    // 4.1666.. = 5.0925.., TRIX (5.0925.. / 4.1666.. - 1) * 100 = 22.2..
    let output = trix_of(&[1.0, 4.0, 7.0, 4.0, 7.0], 2);

    assert!(output[..4].iter().all(|value| value.is_nan()));
    assert!(
        (output[4] - 22.222_222_222_222).abs() < 1e-9,
        "{}",
        output[4]
    );
}

#[test]
fn trix_of_period_1_is_the_one_row_rate_of_change() {
    let output = trix_of(&VALUES, 1);

    assert!(output[0].is_nan());
    assert_eq!(output[1..], rate_of_change(&VALUES, 1)[1..]);
}

#[test]
fn trix_is_zero_on_flat_prices_and_when_the_previous_ema_is_zero() {
    let output = trix_of(&[105.0; 10], 2);
    assert!(output[4..].iter().all(|value| *value == 0.0));

    // A zero previous EMA3 gives 0, not an infinity (as TA-Lib).
    let output = trix_of(&[0.0, 0.0, 0.0, 0.0, 0.0, 3.0], 2);
    assert_eq!(output[4..], [0.0, 0.0]);
}

#[test]
fn trix_rejects_a_zero_period() {
    assert_eq!(trix(&series(&VALUES), 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn trix_needs_three_times_the_period_minus_1_values() {
    assert_eq!(
        trix(&series(&VALUES), 5),
        Err(PytaError::InsufficientData {
            required: 14,
            length: 12,
        })
    );
    assert_eq!(
        trix(&series(&VALUES), usize::MAX),
        Err(PytaError::InsufficientData {
            required: usize::MAX - 1,
            length: 12,
        })
    );
    assert_eq!(
        trix(&series(&[1.0]), 1),
        Err(PytaError::InsufficientData {
            required: 2,
            length: 1,
        })
    );
}

#[test]
fn trix_accepts_minimum_data() {
    // Period 4 needs 11 values and gives one, on the last row.
    let output = trix_of(&VALUES[..11], 4);

    assert!(output[..10].iter().all(|value| value.is_nan()));
    assert!(output[10].is_finite());
}

#[test]
fn trix_is_finite_at_the_magnitude_limit() {
    let values = [
        MAX_ABS_INPUT,
        -MAX_ABS_INPUT,
        MAX_ABS_INPUT,
        MAX_ABS_INPUT,
        1.0,
    ];
    let output = trix_of(&values, 2);

    assert!(output[4].is_finite());
}
