//! SMA against published worked examples (StockCharts ChartSchool), and EMA,
//! WMA, DEMA and MACD against TA-Lib's own output (generated fixtures, see
//! their comments).

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_trend::{dema, ema, macd, sma, wma};
use reference::{assert_matches, assert_output_matches, load};

fn check(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = sma(&input, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
}

#[test]
fn sma_5_matches_the_stockcharts_example() {
    check("sma_5_stockcharts.csv");
}

#[test]
fn sma_10_matches_the_stockcharts_intel_example() {
    check("sma_10_stockcharts.csv");
}

fn check_ema(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = ema(&input, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
}

#[test]
fn ema_10_matches_talib() {
    check_ema("ema_10_talib.csv");
}

#[test]
fn ema_30_matches_talib() {
    check_ema("ema_30_talib.csv");
}

fn check_wma(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = wma(&input, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
}

#[test]
fn wma_10_matches_talib() {
    check_wma("wma_10_talib.csv");
}

#[test]
fn wma_30_matches_talib() {
    check_wma("wma_30_talib.csv");
}

#[test]
fn wma_30_matches_talib_on_the_edge_series() {
    check_wma("wma_30_edge_talib.csv");
}

fn check_dema(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = dema(&input, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
}

#[test]
fn dema_30_matches_talib() {
    check_dema("dema_30_talib.csv");
}

#[test]
fn dema_30_matches_talib_on_the_edge_series() {
    check_dema("dema_30_edge_talib.csv");
}

fn check_macd(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();
    let [fast, slow, signal] = ["fast", "slow", "signal"].map(|name| reference.parameter(name));

    let output = macd(&input, fast, slow, signal).unwrap();

    assert_eq!(output.output_count(), reference.outputs.len());
    for (index, actual) in output.outputs().iter().enumerate() {
        assert_output_matches(actual, &reference, index);
    }
}

#[test]
fn macd_12_26_9_matches_talib() {
    check_macd("macd_12_26_9_talib.csv");
}

#[test]
fn macd_5_35_5_matches_talib() {
    check_macd("macd_5_35_5_talib.csv");
}
