use pyta_core::IndicatorOutput;

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
