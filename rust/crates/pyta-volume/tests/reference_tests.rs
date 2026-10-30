//! Volume indicators against TA-Lib's own output (generated fixtures, see
//! their comments), and Chaikin Money Flow against a hand calculation and
//! fresh window sums (TA-Lib has none).

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_volume::{ad, cmf, obv};
use reference::{Reference, assert_matches, load};

/// Asserts every value is the wheel's own, bit for bit (the fixtures print
/// them with `repr`), and within the fixture's tolerance relative to its
/// magnitude (volume totals reach 1e10, beyond an absolute 1e-9).
fn assert_same_bits(name: &str, actual: &[f64], reference: &Reference) {
    let expected = &reference.outputs[0];
    assert_eq!(actual.len(), expected.len(), "{name}: length");

    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a - e).abs() <= reference.tolerance * e.abs().max(1.0),
            "{name}, index {index}: {a:e} not within tolerance of {e:e}"
        );
        assert!(
            a.to_bits() == e.to_bits(),
            "{name}, index {index}: {a:e} != {e:e}"
        );
    }
}

fn check_obv(name: &str) {
    let reference = load(name);
    let [close, volume] = [0, 1].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = obv(&close, &volume).unwrap();

    // Sums of whole volumes: exact, so TA-Lib's bits.
    assert_same_bits(name, output.values(), &reference);
}

#[test]
fn obv_matches_talib() {
    check_obv("obv_talib.csv");
}

#[test]
fn obv_matches_talib_on_the_edge_series() {
    check_obv("obv_edge_talib.csv");
}

fn check_ad(name: &str) {
    let reference = load(name);
    let [high, low, close, volume] =
        [0, 1, 2, 3].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = ad(&high, &low, &close, &volume).unwrap();

    // TA-Lib's operations in its order: its own doubles.
    assert_same_bits(name, output.values(), &reference);
}

#[test]
fn ad_matches_talib() {
    check_ad("ad_talib.csv");
}

#[test]
fn ad_matches_talib_on_the_edge_series() {
    // Includes a one-price bar off the flat level, flat rows and zero volume.
    check_ad("ad_edge_talib.csv");
}

#[test]
fn cmf_matches_the_hand_calculation() {
    let reference = load("cmf_hand.csv");
    let [high, low, close, volume] =
        [0, 1, 2, 3].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = cmf(&high, &low, &close, &volume, reference.period()).unwrap();

    // Warm-up and row 7's window without volume are NaN on both sides.
    assert_matches(output.values(), &reference);
    assert!(output.values()[7].is_nan());
}

#[test]
fn cmf_matches_fresh_window_sums_on_spy() {
    // The SPY columns of the A/D fixture (no one-price bar among them).
    let reference = load("ad_talib.csv");
    let [high, low, close, volume] = [0, 1, 2, 3].map(|i| reference.columns[i].clone());
    let flow: Vec<f64> = (0..close.len())
        .map(|row| {
            (close[row] - low[row] - (high[row] - close[row])) / (high[row] - low[row])
                * volume[row]
        })
        .collect();
    let columns = [&high, &low, &close, &volume].map(|values| Series::new(values.clone()).unwrap());

    for period in [1, 20, 21, 100] {
        let output = cmf(&columns[0], &columns[1], &columns[2], &columns[3], period).unwrap();

        for end in period..=close.len() {
            let expected = flow[end - period..end].iter().sum::<f64>()
                / volume[end - period..end].iter().sum::<f64>();
            let actual = output.values()[end - 1];
            assert!(
                (actual - expected).abs() <= 1e-12,
                "period {period}, row {}: {actual} != {expected}",
                end - 1
            );
        }
    }
}
