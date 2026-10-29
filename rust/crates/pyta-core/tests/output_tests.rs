//! `IndicatorOutput` accessors.

use pyta_core::{IndicatorOutput, PytaError};

#[test]
fn indicator_output_preserves_warmup_positions() {
    let output = IndicatorOutput::new(vec![f64::NAN, f64::NAN, 2.0, 3.0]);

    assert_eq!(output.len(), 4);
    assert!(output.values()[0].is_nan());
    assert!(output.values()[1].is_nan());
    assert_eq!(output.values()[2], 2.0);
    assert_eq!(output.values()[3], 3.0);
}

#[test]
fn indicator_output_can_be_empty() {
    let output = IndicatorOutput::new(vec![]);

    assert!(output.is_empty());
}

#[test]
fn indicator_output_into_values_returns_all_values() {
    let output = IndicatorOutput::new(vec![1.0, 2.0]);

    assert_eq!(output.into_values(), vec![1.0, 2.0]);
}

#[test]
fn a_single_output_has_one_series() {
    let output = IndicatorOutput::new(vec![1.0, 2.0]);

    assert_eq!(output.output_count(), 1);
    assert_eq!(output.outputs(), [vec![1.0, 2.0]]);
    assert_eq!(output.into_outputs(), vec![vec![1.0, 2.0]]);
}

#[test]
fn several_outputs_keep_their_order() {
    let series = vec![vec![1.0, 2.0], vec![3.0, 4.0], vec![5.0, 6.0]];

    let output = IndicatorOutput::with_outputs(series.clone()).unwrap();

    assert_eq!(output.output_count(), 3);
    assert_eq!(output.len(), 2);
    assert!(!output.is_empty());
    assert_eq!(output.outputs(), series);
    assert_eq!(output.into_outputs(), series);
}

#[test]
fn values_are_the_first_output() {
    let output = IndicatorOutput::with_outputs(vec![vec![1.0, 2.0], vec![3.0, 4.0]]).unwrap();

    assert_eq!(output.values(), [1.0, 2.0]);
    assert_eq!(output.into_values(), vec![1.0, 2.0]);
}

#[test]
fn one_output_through_with_outputs_equals_new() {
    let output = IndicatorOutput::with_outputs(vec![vec![1.0, 2.0]]).unwrap();

    assert_eq!(output, IndicatorOutput::new(vec![1.0, 2.0]));
}

#[test]
fn outputs_of_unequal_length_are_rejected() {
    let result = IndicatorOutput::with_outputs(vec![vec![1.0, 2.0], vec![3.0]]);

    assert_eq!(result, Err(PytaError::LengthMismatch));
}

#[test]
fn zero_outputs_are_rejected() {
    let result = IndicatorOutput::with_outputs(Vec::new());

    assert_eq!(result, Err(PytaError::LengthMismatch));
}
