//! SMA against published worked examples (StockCharts ChartSchool).

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_trend::sma;
use reference::{assert_matches, load};

fn check(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = sma(&input, reference.period).unwrap();

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
