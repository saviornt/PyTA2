//! RSI and CCI against the published StockCharts ChartSchool examples.

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_momentum::{cci, rsi};
use reference::{assert_matches, load};

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
