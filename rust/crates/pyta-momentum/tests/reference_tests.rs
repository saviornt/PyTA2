//! RSI against the published StockCharts ChartSchool RSI-14 example.

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_momentum::rsi;
use reference::{assert_matches, load};

#[test]
fn rsi_14_matches_the_stockcharts_example() {
    let reference = load("rsi_14_stockcharts.csv");
    let input = Series::new(reference.input.clone()).unwrap();

    let output = rsi(&input, reference.period).unwrap();

    assert_matches(output.values(), &reference);
}
