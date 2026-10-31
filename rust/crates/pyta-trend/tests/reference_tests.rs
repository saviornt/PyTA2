//! SMA against published worked examples (StockCharts ChartSchool), and EMA,
//! WMA, DEMA, TEMA, KAMA, MACD, ADX, Parabolic SAR and Aroon against
//! TA-Lib's own output (generated fixtures, see their comments), and
//! Ichimoku Cloud against a hand calculation (TA-Lib has none).

#[path = "../../../test-support/reference.rs"]
mod reference;

use pyta_core::Series;
use pyta_trend::{adx, aroon, dema, ema, ichimoku, kama, macd, sar, sma, tema, wma};
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

fn check_tema(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = tema(&input, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
}

#[test]
fn tema_30_matches_talib() {
    check_tema("tema_30_talib.csv");
}

#[test]
fn tema_30_matches_talib_on_the_edge_series() {
    check_tema("tema_30_edge_talib.csv");
}

fn check_kama(name: &str) {
    let reference = load(name);
    let input = Series::new(reference.input.clone()).unwrap();

    let output = kama(&input, reference.period()).unwrap();

    assert_matches(output.values(), &reference);
    // Measured on 2026-10-29: every value is the wheel's own, bit for bit
    // (the fixture prints them with `repr`, which round-trips). Kept as a
    // regression check on the flat-window reset and the order of operations.
    for (index, (actual, expected)) in output
        .values()
        .iter()
        .zip(&reference.outputs[0])
        .enumerate()
    {
        assert!(
            (actual.is_nan() && expected.is_nan()) || actual.to_bits() == expected.to_bits(),
            "{name}, index {index}: {actual:e} != {expected:e}"
        );
    }
}

#[test]
fn kama_30_matches_talib() {
    check_kama("kama_30_talib.csv");
}

#[test]
fn kama_30_matches_talib_on_the_edge_series() {
    check_kama("kama_30_edge_talib.csv");
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

fn check_adx(name: &str) {
    let reference = load(name);
    let [high, low, close] = [0, 1, 2].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = adx(&high, &low, &close, reference.period()).unwrap();

    assert_eq!(output.output_count(), reference.outputs.len());
    for (index, actual) in output.outputs().iter().enumerate() {
        assert_output_matches(actual, &reference, index);
    }
    // Measured on 2026-10-29: every value of all three outputs is the
    // wheel's own, bit for bit (the fixture prints them with `repr`). Kept
    // as a regression check on TA-Lib 0.8.3's `* (1 / n)` smoothing and its
    // order of operations.
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
fn adx_14_matches_talib() {
    check_adx("adx_14_talib.csv");
}

#[test]
fn adx_14_matches_talib_on_the_edge_series() {
    check_adx("adx_14_edge_talib.csv");
}

fn check_sar(name: &str) {
    let reference = load(name);
    let [high, low] = [0, 1].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = sar(
        &high,
        &low,
        reference.float_parameter("acceleration"),
        reference.float_parameter("maximum"),
    )
    .unwrap();

    assert_matches(output.values(), &reference);
    // TA-Lib writes the step as `fma`, which the wheel's build fuses; this
    // kernel's plain multiply-add rounds twice. Measured on 2026-10-29: 8,
    // 29 and 33 values of the three fixtures differ, each by one unit in
    // the last place (at most 2.1e-16 relative); `f64::mul_add` matched all
    // three bit for bit but made the kernel ~16% slower. Kept as a
    // regression check far tighter than the fixtures' 1e-9.
    for (index, (a, e)) in output
        .values()
        .iter()
        .zip(&reference.outputs[0])
        .enumerate()
        .skip(1)
    {
        assert!(
            (a - e).abs() <= 4e-16 * e.abs(),
            "{name}, index {index}: {a:e} != {e:e}"
        );
    }
}

#[test]
fn sar_0_02_0_2_matches_talib() {
    check_sar("sar_0.02_0.2_talib.csv");
}

#[test]
fn sar_0_01_0_1_matches_talib() {
    check_sar("sar_0.01_0.1_talib.csv");
}

#[test]
fn sar_0_02_0_2_matches_talib_on_the_edge_series() {
    check_sar("sar_0.02_0.2_edge_talib.csv");
}

fn check_aroon(name: &str) {
    let reference = load(name);
    let [high, low] = [0, 1].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = aroon(&high, &low, reference.period()).unwrap();

    assert_eq!(output.output_count(), reference.outputs.len());
    for (index, actual) in output.outputs().iter().enumerate() {
        assert_output_matches(actual, &reference, index);
    }
    // Every value is a multiple of `100 / period` written with TA-Lib's own
    // expressions (the oscillator as `factor * (highest - lowest)`), and
    // the clamp to [0, 100] never binds at period 14, so all three outputs
    // match the wheel's doubles bit for bit.
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
fn aroon_14_matches_talib() {
    check_aroon("aroon_14_talib.csv");
}

#[test]
fn aroon_14_matches_talib_on_the_edge_series() {
    check_aroon("aroon_14_edge_talib.csv");
}

#[test]
fn ichimoku_matches_the_hand_calculation() {
    // No reference library has Ichimoku with unshifted spans (TA-Lib has no
    // Ichimoku); the fixture is derived by hand with exact fractions (see its
    // comments), all exact doubles.
    let reference = load("ichimoku_hand.csv");
    let [high, low, close] = [0, 1, 2].map(|i| Series::new(reference.columns[i].clone()).unwrap());

    let output = ichimoku(
        &high,
        &low,
        &close,
        reference.parameter("tenkan"),
        reference.parameter("kijun"),
        reference.parameter("senkou"),
        false,
    )
    .unwrap();

    assert_eq!(output.output_count(), 5);
    for (index, line) in output.outputs().iter().enumerate() {
        assert_output_matches(line, &reference, index);
    }
}
