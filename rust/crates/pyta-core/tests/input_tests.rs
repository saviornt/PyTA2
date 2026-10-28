use pyta_common::MAX_ABS_INPUT;
use pyta_core::{Ohlcv, PytaError, Series};

#[test]
fn series_accepts_valid_values() {
    let series = Series::new(vec![1.0, 2.0, 3.0]).unwrap();

    assert_eq!(series.len(), 3);
    assert_eq!(series.values(), &[1.0, 2.0, 3.0]);
}

#[test]
fn series_rejects_empty_input() {
    let result = Series::new(vec![]);

    assert_eq!(result, Err(PytaError::EmptyInput));
}

#[test]
fn series_rejects_nan() {
    let result = Series::new(vec![1.0, f64::NAN, 3.0]);

    assert_eq!(result, Err(PytaError::NonFiniteValue { index: 1 }));
}

#[test]
fn series_rejects_infinity() {
    let result = Series::new(vec![1.0, f64::INFINITY]);

    assert_eq!(result, Err(PytaError::NonFiniteValue { index: 1 }));
}

#[test]
fn series_reports_first_non_finite_index_across_blocks() {
    // Spans several validation blocks plus a partial tail.
    for index in [0, 63, 64, 130, 199] {
        let mut values = vec![1.0; 200];
        values[index] = f64::NEG_INFINITY;
        values[199] = f64::NAN;

        let expected = Err(PytaError::NonFiniteValue { index });
        assert_eq!(Series::new(values.clone()), expected);
        assert_eq!(Series::from_slice(&values), expected);
    }
}

#[test]
fn from_slice_matches_new() {
    let values: Vec<f64> = (0..1_000).map(|i| f64::from(i).sin()).collect();

    assert_eq!(Series::from_slice(&values), Series::new(values.clone()));
    assert_eq!(Series::from_slice(&[]), Err(PytaError::EmptyInput));
}

#[test]
fn series_accepts_values_up_to_the_magnitude_limit() {
    let values = [
        MAX_ABS_INPUT,
        -MAX_ABS_INPUT,
        f64::MIN_POSITIVE,
        -0.0,
        5e-324,
    ];

    assert!(Series::new(values.to_vec()).is_ok());
    assert!(Series::from_slice(&values).is_ok());
}

#[test]
fn series_rejects_finite_values_beyond_the_magnitude_limit() {
    let just_above = MAX_ABS_INPUT.next_up();

    for value in [just_above, -just_above, f64::MAX, f64::MIN] {
        // Spans several validation blocks plus a partial tail.
        for index in [0, 63, 64, 130, 199] {
            let mut values = vec![1.0; 200];
            values[index] = value;

            let expected = Err(PytaError::ValueOutOfRange { index });
            assert_eq!(Series::new(values.clone()), expected);
            assert_eq!(Series::from_slice(&values), expected);
        }
    }
}

#[test]
fn series_reports_whichever_invalid_value_comes_first() {
    let values = [1.0, f64::NAN, f64::MAX];
    assert_eq!(
        Series::from_slice(&values),
        Err(PytaError::NonFiniteValue { index: 1 })
    );

    let values = [1.0, f64::MAX, f64::NAN];
    assert_eq!(
        Series::from_slice(&values),
        Err(PytaError::ValueOutOfRange { index: 1 })
    );
}

#[test]
fn out_of_range_message_names_the_index_and_limit() {
    let message = PytaError::ValueOutOfRange { index: 7 }.to_string();

    assert_eq!(
        message,
        "value at index 7 is too large in magnitude; values must be between -1e290 and 1e290"
    );
}

#[test]
fn ohlcv_rejects_mismatched_lengths() {
    let short = Series::new(vec![1.0]).unwrap();
    let long = Series::new(vec![1.0, 2.0]).unwrap();

    let result = Ohlcv::new(short.clone(), long, short.clone(), short.clone(), short);

    assert_eq!(result, Err(PytaError::LengthMismatch));
}
