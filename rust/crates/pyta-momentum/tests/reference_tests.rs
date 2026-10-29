//! RSI and CCI against the published StockCharts ChartSchool examples, and
//! Stochastic against TA-Lib's own output (generated fixtures, see their
//! comments).

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_momentum::{cci, rsi, stoch};
use reference::{assert_matches, assert_output_matches, load};

#[test]
fn rsi_14_matches_the_stockcharts_example() {
    let reference = load("rsi_14_stockcharts.csv");
    let input = Series::new(reference.input.clone()).unwrap();

    let output = rsi(&input, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
}

#[test]
fn cci_20_matches_the_stockcharts_example() {
    let reference = load("cci_20_stockcharts.csv");
    let [high, low, close] = [0, 1, 2].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = cci(&high, &low, &close, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
}

fn check_stoch(name: &str) {
    let reference = load(name);
    let [high, low, close] = [0, 1, 2].map(|i| Series::new(reference.columns[i].clone()).unwrap());
    let [k, k_smooth, d] = ["k", "k_smooth", "d"].map(|name| reference.parameter(name));

    let output = stoch(&high, &low, &close, k, k_smooth, d).unwrap();

    assert_eq!(output.output_count(), reference.outputs.len());
    for (index, actual) in output.outputs().iter().enumerate() {
        assert_output_matches(actual, &reference, index);
    }
    // Measured on 2026-10-29: every value of both outputs is the wheel's
    // own, bit for bit (the fixtures print them with `repr`). Kept as a
    // regression check on TA-Lib's running-sum SMA and its order of
    // operations (divide by the range, then scale by 100).
    for (output, (actual, expected)) in output.outputs().iter().zip(&reference.outputs).enumerate()
    {
        for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
            assert!(
                (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
                "{name}, output {output}, index {index}: {a:e} != {e:e}"
            );
        }
    }
}

#[test]
fn stoch_14_3_3_matches_talib() {
    check_stoch("stoch_14_3_3_talib.csv");
}

#[test]
fn stoch_5_3_3_matches_talib() {
    check_stoch("stoch_5_3_3_talib.csv");
}

#[test]
fn stoch_14_3_3_matches_talib_on_the_edge_series() {
    check_stoch("stoch_14_3_3_edge_talib.csv");
}
