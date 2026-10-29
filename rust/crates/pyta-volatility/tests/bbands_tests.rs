//! BBANDS kernel: formula, outputs, warm-up, parameters and edge cases.

use pyta_common::MAX_ABS_INPUT;
use pyta_core::{PytaError, Series};
use pyta_volatility::{bbands, stddev};

fn series(values: &[f64]) -> Series {
    Series::new(values.to_vec()).unwrap()
}

/// Upper, middle and lower bands.
fn bands_of(values: &[f64], period: usize, k: f64) -> [Vec<f64>; 3] {
    let outputs = bbands(&series(values), period, k).unwrap().into_outputs();
    outputs.try_into().expect("three outputs")
}

// Windows of 4: [2, 4, 4, 4] mean 3.5, variance 0.75;
// [4, 4, 4, 5] mean 4.25, variance 0.1875; [4, 4, 5, 5] mean 4.5,
// variance 0.25; [4, 5, 5, 7] mean 5.25, variance 1.1875;
// [5, 5, 7, 9] mean 6.5, variance 2.75.
const VALUES: [f64; 8] = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];

#[test]
fn bbands_returns_three_outputs_with_input_length_and_shared_warm_up() {
    let output = bbands(&series(&VALUES), 4, 2.0).unwrap();

    assert_eq!(output.output_count(), 3);
    for band in output.outputs() {
        assert_eq!(band.len(), 8);
        assert!(band[..3].iter().all(|value| value.is_nan()));
        assert!(band[3..].iter().all(|value| value.is_finite()));
    }
}

#[test]
fn bbands_matches_a_hand_calculation() {
    let [upper, middle, lower] = bands_of(&VALUES, 4, 2.0);
    let means = [3.5, 4.25, 4.5, 5.25, 6.5];
    let deviations = [0.75_f64, 0.1875, 0.25, 1.1875, 2.75].map(f64::sqrt);

    for (index, (mean, deviation)) in means.iter().zip(deviations).enumerate() {
        let row = index + 3;
        assert!((middle[row] - mean).abs() <= 1e-15, "middle {row}");
        assert!(
            (upper[row] - (mean + 2.0 * deviation)).abs() <= 1e-14,
            "upper {row}"
        );
        assert!(
            (lower[row] - (mean - 2.0 * deviation)).abs() <= 1e-14,
            "lower {row}"
        );
    }
}

#[test]
fn bbands_bands_are_k_stddevs_from_the_middle() {
    // The band width is exactly STDDEV's value with the same `k`.
    for k in [1.0, 2.0, 2.5] {
        let [upper, middle, lower] = bands_of(&VALUES, 4, k);
        let width = stddev(&series(&VALUES), 4, k).unwrap().into_values();

        for row in 3..8 {
            assert_eq!(upper[row], middle[row] + width[row]);
            assert_eq!(lower[row], middle[row] - width[row]);
        }
    }
}

#[test]
fn bbands_uses_the_population_deviation() {
    // The whole series: mean 5, squared deviations sum to 32, so the
    // population deviation is sqrt(32 / 8) = 2 (the sample one would be
    // sqrt(32 / 7)).
    let [upper, middle, lower] = bands_of(&VALUES, 8, 1.0);

    assert_eq!((upper[7], middle[7], lower[7]), (7.0, 5.0, 3.0));
}

#[test]
fn bbands_rejects_a_period_below_two() {
    for period in [0, 1] {
        assert_eq!(
            bbands(&series(&VALUES), period, 2.0),
            Err(PytaError::InvalidParameter {
                name: "period",
                minimum: 2,
                value: period,
            })
        );
    }
}

#[test]
fn bbands_rejects_a_k_that_is_not_a_finite_positive_number() {
    for k in [0.0, -0.0, -2.0, f64::INFINITY, f64::NEG_INFINITY] {
        assert_eq!(
            bbands(&series(&VALUES), 4, k),
            Err(PytaError::InvalidFloatParameter {
                name: "k",
                value: k
            })
        );
    }

    assert!(matches!(
        bbands(&series(&VALUES), 4, f64::NAN),
        Err(PytaError::InvalidFloatParameter { name: "k", value }) if value.is_nan()
    ));
}

#[test]
fn bbands_checks_the_period_before_k() {
    assert!(matches!(
        bbands(&series(&VALUES), 1, -1.0),
        Err(PytaError::InvalidParameter { .. })
    ));
}

#[test]
fn bbands_rejects_a_period_longer_than_the_series() {
    assert_eq!(
        bbands(&series(&[1.0, 2.0, 3.0]), 4, 2.0),
        Err(PytaError::PeriodExceedsLength {
            period: 4,
            length: 3,
        })
    );
}

#[test]
fn bbands_accepts_minimum_data() {
    let [upper, middle, lower] = bands_of(&[1.0, 3.0], 2, 2.0);

    assert!(upper[0].is_nan() && middle[0].is_nan() && lower[0].is_nan());
    assert_eq!((upper[1], middle[1], lower[1]), (4.0, 2.0, 0.0));
}

#[test]
fn bbands_gives_three_equal_bands_for_a_flat_series() {
    // The deviation is snapped to exactly 0, as TA-Lib gives, so every band
    // equals the middle one, whatever `k`.
    for level in [0.1, 101.37, 105.0, 1.0e-200, -7.3e12, 0.0] {
        let [upper, middle, lower] = bands_of(&[level; 30], 7, 2.0);

        for row in 6..30 {
            assert_eq!(upper[row], middle[row], "level {level}, row {row}");
            assert_eq!(lower[row], middle[row], "level {level}, row {row}");
        }
    }
}

#[test]
fn bbands_is_finite_at_the_magnitude_limit() {
    let values = [MAX_ABS_INPUT, -MAX_ABS_INPUT, MAX_ABS_INPUT, -MAX_ABS_INPUT];
    let [upper, middle, lower] = bands_of(&values, 2, 1.0);

    for row in 1..4 {
        assert_eq!(middle[row], 0.0);
        assert!((upper[row] / MAX_ABS_INPUT - 1.0).abs() <= 1e-15);
        assert!((lower[row] / MAX_ABS_INPUT + 1.0).abs() <= 1e-15);
    }
}
