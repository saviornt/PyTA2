use pyta_core::IndicatorOutput;

#[test]
fn indicator_output_preserves_warmup_positions() {
    let output = IndicatorOutput::new(vec![
        None,
        None,
        Some(2.0),
        Some(3.0),
    ]);

    assert_eq!(output.len(), 4);
    assert_eq!(output.values()[0], None);
    assert_eq!(output.values()[1], None);
    assert_eq!(output.values()[2], Some(2.0));
    assert_eq!(output.values()[3], Some(3.0));
}

#[test]
fn indicator_output_can_be_empty() {
    let output = IndicatorOutput::new(vec![]);

    assert!(output.is_empty());
}