//! Volume indicators against TA-Lib's own output (generated fixtures, see
//! their comments).

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_volume::obv;
use reference::{Reference, load};

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
