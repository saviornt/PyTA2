//! Reads the reference examples in `tests/fixtures/`.
//!
//! Included by the kernel crates' reference tests with `#[path]`, so the
//! Rust and Python tests check the same files. Each fixture is a CSV file
//! whose `#` comment lines cite the source and give the parameters as
//! `name: value` (`period:`, or `fast:`, `slow:` and `signal:` for MACD) and
//! `tolerance:`. Its columns are `label`, one or more input columns, and one
//! or more output columns: `expected` for a single-output indicator, or
//! `expected_<output>` for each output in documented order. An empty output
//! value is warm-up (NaN). A single-column example names its input column
//! `input`; a multi-column one names each column by role
//! (`high,low,close`), in the indicator's slot order.

use std::path::Path;

/// One reference example: input, expected outputs, parameters and tolerance.
pub struct Reference {
    pub tolerance: f64,
    /// The first input column (the only one for a single-column example).
    pub input: Vec<f64>,
    /// Every input column, in the file's order.
    #[allow(dead_code, reason = "single-column reference tests read only `input`")]
    pub columns: Vec<Vec<f64>>,
    /// Every output column, in the file's order (one for a single-output
    /// example).
    pub outputs: Vec<Vec<f64>>,
    /// Every `name: value` comment, in file order.
    comments: Vec<(String, String)>,
}

#[allow(
    dead_code,
    reason = "each crate's reference tests use only the accessors they need"
)]
impl Reference {
    /// The `period:` parameter.
    pub fn period(&self) -> usize {
        self.parameter("period")
    }

    /// A whole-number parameter given as a `name: value` comment.
    pub fn parameter(&self, name: &str) -> usize {
        let (_, value) = self
            .comments
            .iter()
            .rfind(|(key, _)| key == name)
            .unwrap_or_else(|| panic!("fixture has no `{name}:` comment"));

        value
            .parse()
            .unwrap_or_else(|_| panic!("`{name}: {value}` is not a whole number"))
    }
}

/// Whether a header column holds an output (`expected` or `expected_<name>`).
fn is_output(column: &str) -> bool {
    column == "expected" || column.starts_with("expected_")
}

fn parse_number(field: &str, what: &str) -> f64 {
    match field {
        "" => f64::NAN,
        value => value
            .parse()
            .unwrap_or_else(|_| panic!("{what} is not a number: {value:?}")),
    }
}

/// Loads `tests/fixtures/<name>` from the repository root.
pub fn load(name: &str) -> Reference {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../tests/fixtures")
        .join(name);
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()));

    let mut comments = Vec::new();
    // Whether each column after `label` is an output, from the header.
    let mut header: Option<Vec<bool>> = None;
    let mut columns: Vec<Vec<f64>> = Vec::new();
    let mut outputs: Vec<Vec<f64>> = Vec::new();

    for line in text.lines() {
        if let Some(comment) = line.strip_prefix('#') {
            if let Some((key, value)) = comment.trim().split_once(": ") {
                comments.push((key.to_owned(), value.trim().to_owned()));
            }
            continue;
        }
        if line.is_empty() {
            continue;
        }

        let [_label, fields @ ..] = &line.split(',').collect::<Vec<_>>()[..] else {
            unreachable!("split yields at least one field");
        };

        let Some(kinds) = &header else {
            let kinds: Vec<bool> = fields.iter().map(|field| is_output(field)).collect();
            let output_count = kinds.iter().filter(|output| **output).count();
            assert!(output_count > 0, "header has no expected column: {line}");
            assert!(
                output_count < kinds.len(),
                "header has no input column: {line}"
            );
            columns = vec![Vec::new(); kinds.len() - output_count];
            outputs = vec![Vec::new(); output_count];
            header = Some(kinds);
            continue;
        };

        assert_eq!(
            fields.len(),
            kinds.len(),
            "row has the wrong field count: {line}"
        );
        let (mut input, mut output) = (columns.iter_mut(), outputs.iter_mut());
        for (field, is_output) in fields.iter().zip(kinds) {
            if *is_output {
                let column = output.next().expect("one column per output");
                column.push(parse_number(field, "an expected value"));
            } else {
                let column = input.next().expect("one column per input");
                assert!(!field.is_empty(), "input value is missing: {line}");
                column.push(parse_number(field, "an input value"));
            }
        }
    }

    let tolerance = comments
        .iter()
        .rfind(|(key, _)| key == "tolerance")
        .and_then(|(_, value)| value.parse().ok())
        .expect("fixture has a tolerance");

    Reference {
        tolerance,
        input: columns[0].clone(),
        columns,
        outputs,
        comments,
    }
}

/// Asserts that `actual` matches the example's first output within its
/// tolerance, with NaN exactly where the example has warm-up.
#[allow(
    dead_code,
    reason = "multi-output reference tests use `assert_output_matches`"
)]
pub fn assert_matches(actual: &[f64], reference: &Reference) {
    assert_output_matches(actual, reference, 0);
}

/// Like [`assert_matches`], for the example's output number `output`.
#[allow(
    dead_code,
    reason = "single-output reference tests use `assert_matches`"
)]
pub fn assert_output_matches(actual: &[f64], reference: &Reference, output: usize) {
    let expected = &reference.outputs[output];
    assert_eq!(actual.len(), expected.len());

    for (index, (got, want)) in actual.iter().zip(expected).enumerate() {
        if want.is_nan() {
            assert!(
                got.is_nan(),
                "output {output}, index {index}: expected warm-up NaN, got {got}"
            );
        } else {
            assert!(
                (got - want).abs() <= reference.tolerance,
                "output {output}, index {index}: got {got}, reference {want} (tolerance {})",
                reference.tolerance
            );
        }
    }
}
