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
fn series_accepts_extreme_finite_values() {
    let values = [f64::MAX, f64::MIN, f64::MIN_POSITIVE, -0.0, 5e-324];

    assert!(Series::new(values.to_vec()).is_ok());
    assert!(Series::from_slice(&values).is_ok());
}

#[test]
fn ohlcv_rejects_mismatched_lengths() {
    let short = Series::new(vec![1.0]).unwrap();
    let long = Series::new(vec![1.0, 2.0]).unwrap();

    let result = Ohlcv::new(short.clone(), long, short.clone(), short.clone(), short);

    assert_eq!(result, Err(PytaError::LengthMismatch));
}
