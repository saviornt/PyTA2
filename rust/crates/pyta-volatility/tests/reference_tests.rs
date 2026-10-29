//! ATR against TA-Lib's own output (generated fixtures, see their comments).

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_volatility::atr;
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
