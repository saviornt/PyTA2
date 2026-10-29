//! `PytaError` messages and equality.
//!
//! The messages reach Python users verbatim (as `ValueError` or
//! `RuntimeError`), so each one must name the problem and, where possible,
//! the fix.

use pyta_core::{PytaError, PytaResult};

#[test]
fn messages_name_the_problem_and_the_values_involved() {
    let cases = [
        (
            PytaError::EmptyInput,
            "input series is empty; provide at least one value",
        ),
        (
            PytaError::NonFiniteValue { index: 7 },
            "non-finite value (NaN or infinity) at index 7; only leading NaN values are skipped",
        ),
        (
            PytaError::LengthMismatch,
            "input series have mismatched lengths",
        ),
        (PytaError::InvalidPeriod, "period must be at least 1"),
        (
            PytaError::PeriodExceedsLength {
                period: 20,
                length: 5,
            },
            "period (20) exceeds the series length (5); use a smaller period or provide more data",
        ),
        (
            PytaError::InsufficientData {
                required: 15,
                length: 3,
            },
            "not enough data: at least 15 values are required, got 3",
        ),
        (
            PytaError::InvalidParameter {
                name: "fast",
                minimum: 2,
                value: 1,
            },
            "fast must be at least 2, got 1",
        ),
        (
            PytaError::InvalidFloatParameter {
                name: "k",
                value: -1.5,
            },
            "k must be a finite number greater than 0, got -1.5",
        ),
        (
            PytaError::ColumnCount {
                expected: 3,
                actual: 1,
            },
            "expected 3 input columns, got 1",
        ),
        (
            PytaError::ExecutionFailed,
            "indicator execution failed before returning a result",
        ),
    ];

    for (error, expected) in cases {
        assert_eq!(error.to_string(), expected);
    }
}

#[test]
fn errors_compare_by_variant_and_fields() {
    assert_eq!(
        PytaError::NonFiniteValue { index: 1 },
        PytaError::NonFiniteValue { index: 1 }
    );
    assert_ne!(
        PytaError::NonFiniteValue { index: 1 },
        PytaError::NonFiniteValue { index: 2 }
    );
    assert_ne!(PytaError::EmptyInput, PytaError::InvalidPeriod);
}

#[test]
fn errors_clone_equal() {
    let error = PytaError::PeriodExceedsLength {
        period: 3,
        length: 2,
    };

    assert_eq!(error.clone(), error);
}

#[test]
fn errors_are_std_errors_without_a_source() {
    let error: Box<dyn std::error::Error> = Box::new(PytaError::EmptyInput);

    assert!(error.source().is_none());
}

#[test]
fn result_alias_carries_the_error() {
    let result: PytaResult<f64> = Err(PytaError::InvalidPeriod);

    assert_eq!(result, Err(PytaError::InvalidPeriod));
}
