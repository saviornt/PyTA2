//! Reads the published reference examples in `tests/fixtures/`.
//!
//! Included by the kernel crates' reference tests with `#[path]`, so the
//! Rust and Python tests check the same files. Each fixture is a CSV file
//! whose `#` comment lines cite the source and give `period:` and
//! `tolerance:`; its columns are `label`, one or more input columns, and
//! `expected`, with an empty `expected` for warm-up rows (NaN). A
//! single-column example names its input column `input`; a multi-column one
//! names each column by role (`high,low,close`), in the indicator's slot order.

use std::path::Path;

/// One published example: input, expected output, period and tolerance.
pub struct Reference {
    pub period: usize,
    pub tolerance: f64,
    /// The first input column (the only one for a single-column example).
    pub input: Vec<f64>,
    /// Every input column, in the file's order.
    #[allow(dead_code, reason = "single-column reference tests read only `input`")]
    pub columns: Vec<Vec<f64>>,
    pub expected: Vec<f64>,
}

/// Loads `tests/fixtures/<name>` from the repository root.
pub fn load(name: &str) -> Reference {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../tests/fixtures")
        .join(name);
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()));

    let mut period = None;
    let mut tolerance = None;
    let mut columns: Vec<Vec<f64>> = Vec::new();
    let mut expected = Vec::new();

    for line in text.lines() {
        if let Some(comment) = line.strip_prefix('#') {
            match comment.trim().split_once(": ") {
                Some(("period", value)) => period = value.parse().ok(),
                Some(("tolerance", value)) => tolerance = value.parse().ok(),
                _ => {}
            }
            continue;
        }

        let fields: Vec<&str> = line.split(',').collect();
        if line.is_empty() {
            continue;
        }
        let [_label, inputs @ .., last] = &fields[..] else {
            panic!("row has too few fields: {line}");
        };
        if *last == "expected" {
            columns = vec![Vec::new(); inputs.len()];
            continue;
        }

        for (column, field) in columns.iter_mut().zip(inputs) {
            column.push(field.parse().expect("input is a number"));
        }
        expected.push(match *last {
            "" => f64::NAN,
            value => value.parse().expect("expected is a number or empty"),
        });
    }

    Reference {
        period: period.expect("fixture has a period"),
        tolerance: tolerance.expect("fixture has a tolerance"),
        input: columns[0].clone(),
        columns,
        expected,
    }
}

/// Asserts that `actual` matches the example within its tolerance, with
/// NaN exactly where the example has warm-up.
pub fn assert_matches(actual: &[f64], reference: &Reference) {
    assert_eq!(actual.len(), reference.expected.len());

    for (index, (got, want)) in actual.iter().zip(&reference.expected).enumerate() {
        if want.is_nan() {
            assert!(
                got.is_nan(),
                "index {index}: expected warm-up NaN, got {got}"
            );
        } else {
            assert!(
                (got - want).abs() <= reference.tolerance,
                "index {index}: got {got}, published {want} (tolerance {})",
                reference.tolerance
            );
        }
    }
}
