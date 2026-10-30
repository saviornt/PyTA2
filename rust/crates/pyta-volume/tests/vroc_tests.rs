//! Volume ROC kernel: formula, warm-up, parameters and edge cases.

use pyta_core::{PytaError, Series};
use pyta_volume::vroc;

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

fn vroc_of(values: &[f64], period: usize) -> Vec<f64> {
    vroc(&series(values), period).unwrap().into_values()
}

const VOLUME: [f64; 6] = [100.0, 200.0, 50.0, 0.0, 300.0, 150.0];

#[test]
fn vroc_matches_a_hand_calculation() {
    // Period 2: 50 / 100, 0 / 200, 300 / 50, 150 / 0 (zero base -> 0).
    let output = vroc_of(&VOLUME, 2);

    assert!(output[..2].iter().all(|value| value.is_nan()));
    assert_eq!(output[2..], [-50.0, -100.0, 500.0, 0.0]);
}

#[test]
fn vroc_has_input_length_and_period_warm_up() {
    for period in 1..=5 {
        let output = vroc_of(&VOLUME, period);

        assert_eq!(output.len(), VOLUME.len());
        assert!(output[..period].iter().all(|value| value.is_nan()));
        assert!(output[period..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn vroc_is_bit_for_bit_the_shared_rate_of_change() {
    let volume = [1234.0, 987.0, 1500.5, 3.0, 77.0, 4.25e6, 0.5];
    for period in 1..volume.len() {
        let expected = pyta_core::kernels::rate_of_change(&volume, period);
        let actual = vroc_of(&volume, period);

        for (a, e) in actual.iter().zip(&expected) {
            assert!((a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits());
        }
    }
}

#[test]
fn vroc_rejects_a_zero_period() {
    assert_eq!(vroc(&series(&VOLUME), 0), Err(PytaError::InvalidPeriod));
}

#[test]
fn vroc_needs_period_plus_1_values() {
    assert_eq!(
        vroc(&series(&VOLUME), 6),
        Err(PytaError::InsufficientData {
            required: 7,
            length: 6,
        })
    );
    assert_eq!(
        vroc(&series(&VOLUME), usize::MAX),
        Err(PytaError::InsufficientData {
            required: usize::MAX,
            length: 6,
        })
    );
    // `period + 1` values give one value, on the last row.
    assert_eq!(vroc_of(&VOLUME, 5)[5], 50.0);
}
