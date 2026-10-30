//! RSI and CCI against the published StockCharts ChartSchool examples, and
//! Stochastic, Williams %R, ROC, MFI, TRIX and the Ultimate Oscillator against
//! TA-Lib's own output (generated fixtures, see their comments).

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_momentum::{cci, mfi, roc, rsi, stoch, trix, ultosc, willr};
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

fn check_willr(name: &str) {
    let reference = load(name);
    let [high, low, close] = [0, 1, 2].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = willr(&high, &low, &close, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
    // Every value is the wheel's own, bit for bit (the fixtures print them
    // with `repr`), signed zeros included: kept as a regression check on
    // TA-Lib's order of operations (divide by the range, then scale by -100).
    for (index, (a, e)) in output
        .values()
        .iter()
        .zip(&reference.outputs[0])
        .enumerate()
    {
        assert!(
            (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
            "{name}, index {index}: {a:e} != {e:e}"
        );
    }
}

#[test]
fn willr_14_matches_talib() {
    check_willr("willr_14_talib.csv");
}

#[test]
fn willr_14_matches_talib_on_the_edge_series() {
    check_willr("willr_14_edge_talib.csv");
}

fn check_roc(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = roc(&input, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
    // Every value is the wheel's own, bit for bit (the fixtures print them
    // with `repr`): TA-Lib's `(x / base - 1) * 100`, and 0 for the edge
    // series' zero base.
    for (index, (a, e)) in output
        .values()
        .iter()
        .zip(&reference.outputs[0])
        .enumerate()
    {
        assert!(
            (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
            "{name}, index {index}: {a:e} != {e:e}"
        );
    }
}

#[test]
fn roc_10_matches_talib() {
    check_roc("roc_10_talib.csv");
}

#[test]
fn roc_10_matches_talib_on_the_edge_series() {
    check_roc("roc_10_edge_talib.csv");
}

/// Asserts every value is the wheel's own, bit for bit (the fixtures print
/// them with `repr`).
fn assert_same_bits(name: &str, actual: &[f64], expected: &[f64]) {
    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
            "{name}, index {index}: {a:e} != {e:e}"
        );
    }
}

fn check_mfi(name: &str) {
    let reference = load(name);
    let [high, low, close, volume] =
        [0, 1, 2, 3].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = mfi(&high, &low, &close, &volume, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
    // TA-Lib's own sums, residue resets and divisions, in its order.
    assert_same_bits(name, output.values(), &reference.outputs[0]);
}

#[test]
fn mfi_14_matches_talib() {
    check_mfi("mfi_14_talib.csv");
}

#[test]
fn mfi_14_matches_talib_on_the_edge_series() {
    check_mfi("mfi_14_edge_talib.csv");
}

fn check_trix(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = trix(&input, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
    // TA-Lib 0.8.3 writes its EMA update as `fma(beta, previous, k * value)`
    // where PyTA uses `(value - previous) * k + previous`, so a few values
    // differ in their last bits (measured at most 3.7e-13 relative).
    for (index, (a, e)) in output
        .values()
        .iter()
        .zip(&reference.outputs[0])
        .enumerate()
    {
        assert!(
            (a.is_nan() && e.is_nan()) || (a - e).abs() <= 1e-12 * e.abs().max(1e-3),
            "{name}, index {index}: {a:e} != {e:e}"
        );
    }
}

#[test]
fn trix_30_matches_talib() {
    check_trix("trix_30_talib.csv");
}

#[test]
fn trix_15_matches_talib() {
    check_trix("trix_15_talib.csv");
}

#[test]
fn trix_30_matches_talib_on_the_edge_series() {
    check_trix("trix_30_edge_talib.csv");
}

fn check_ultosc(name: &str) {
    let reference = load(name);
    let [high, low, close] = [0, 1, 2].map(|i| Series::new(reference.columns[i].clone()).unwrap());
    let [short, medium, long] = ["short", "medium", "long"].map(|name| reference.parameter(name));

    let output = ultosc(&high, &low, &close, short, medium, long).unwrap();

    assert_matches(output.values(), &reference);
    // TA-Lib's own running sums, resets and weighting, in its order.
    assert_same_bits(name, output.values(), &reference.outputs[0]);
}

#[test]
fn ultosc_7_14_28_matches_talib() {
    check_ultosc("ultosc_7_14_28_talib.csv");
}

#[test]
fn ultosc_7_14_28_matches_talib_on_the_edge_series() {
    check_ultosc("ultosc_7_14_28_edge_talib.csv");
}
