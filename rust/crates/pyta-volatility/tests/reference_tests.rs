//! ATR and STDDEV against TA-Lib's own output (generated fixtures, see their comments).

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_volatility::{atr, stddev};
use reference::{assert_matches, load};

fn check_atr(name: &str) {
    let reference = load(name);
    let [high, low, close] = [0, 1, 2].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = atr(&high, &low, &close, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
}

#[test]
fn atr_14_matches_talib_on_spy() {
    check_atr("atr_14_talib.csv");
}

#[test]
fn atr_14_matches_talib_on_the_edge_series() {
    check_atr("atr_14_edge_talib.csv");
}

fn check_stddev(name: &str) -> (Vec<f64>, Vec<f64>) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = stddev(&input, reference.period(), reference.float_parameter("k")).unwrap();

    assert_matches(output.values(), &reference);
    (output.into_values(), reference.outputs[0].clone())
}

#[test]
fn stddev_5_1_matches_talib_on_spy() {
    check_stddev("stddev_5_1_talib.csv");
}

#[test]
fn stddev_20_2_matches_talib_on_spy() {
    check_stddev("stddev_20_2_talib.csv");
}

#[test]
fn stddev_5_1_matches_talib_on_the_edge_series() {
    let (actual, expected) = check_stddev("stddev_5_1_edge_talib.csv");

    // TA-Lib gives exactly 0 on the flat stretch; so does PyTA.
    let zeros: Vec<usize> = (0..expected.len())
        .filter(|&i| expected[i] == 0.0)
        .collect();
    assert!(!zeros.is_empty(), "the edge series has a flat stretch");
    for index in zeros {
        assert_eq!(actual[index], 0.0, "index {index}");
    }
}
