//! SMA, EMA, WMA, DEMA, TEMA, KAMA, MACD, ADX, Parabolic SAR, Aroon and
//! Ichimoku Cloud invariants that must hold for any valid input.

use proptest::prelude::*;
use pyta_core::{Series, kernels};
use pyta_trend::{adx, aroon, dema, ema, ichimoku, kama, macd, sar, sma, tema, wma};

/// A series of 1 to 300 prices and a period that fits it.
fn series_and_period() -> impl Strategy<Value = (Vec<f64>, usize)> {
    prop::collection::vec(-1.0e6..1.0e6_f64, 1..300).prop_flat_map(|values| {
        let length = values.len();
        (Just(values), 1..=length)
    })
}

proptest! {
    #[test]
    fn output_length_and_warm_up_are_exact((values, period) in series_and_period()) {
        let output = sma(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        prop_assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn each_value_lies_within_its_window((values, period) in series_and_period()) {
        let output = sma(&Series::new(values.clone()).unwrap(), period).unwrap();

        for (index, average) in output.values().iter().enumerate().skip(period - 1) {
            let window = &values[index + 1 - period..=index];
            let low = window.iter().copied().fold(f64::INFINITY, f64::min);
            let high = window.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            // Rounding in the running sum may step just outside the range.
            let slack = 1.0e-9 * high.abs().max(low.abs()).max(1.0);

            prop_assert!(
                *average >= low - slack && *average <= high + slack,
                "index {}: {} outside [{}, {}]", index, average, low, high
            );
        }
    }

    #[test]
    fn constant_input_gives_a_constant_average(
        value in -1.0e6..1.0e6_f64,
        length in 1_usize..300,
        period_seed in 0_usize..300,
    ) {
        let period = period_seed % length + 1;
        let output = sma(&Series::new(vec![value; length]).unwrap(), period).unwrap();

        for average in &output.values()[period - 1..] {
            prop_assert!((average - value).abs() <= 1.0e-12 * value.abs().max(1.0));
        }
    }
}

/// A series and MACD parameters that fit it; `fast` and `slow` come in
/// either order, since the kernel swaps them.
fn series_and_macd_parameters() -> impl Strategy<Value = (Vec<f64>, usize, usize, usize)> {
    (2_usize..40, 2_usize..40, 1_usize..20).prop_flat_map(|(fast, slow, signal)| {
        let required = fast.max(slow) + signal - 1;
        (
            prop::collection::vec(-1.0e6..1.0e6_f64, required..required + 200),
            Just(fast),
            Just(slow),
            Just(signal),
        )
    })
}

proptest! {
    #[test]
    fn ema_output_length_and_warm_up_are_exact((values, period) in series_and_period()) {
        let output = ema(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        prop_assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn ema_stays_within_the_range_of_its_input((values, period) in series_and_period()) {
        let output = ema(&Series::new(values.clone()).unwrap(), period).unwrap();
        let low = values.iter().copied().fold(f64::INFINITY, f64::min);
        let high = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let slack = 1.0e-9 * high.abs().max(low.abs()).max(1.0);

        for average in &output.values()[period - 1..] {
            prop_assert!(*average >= low - slack && *average <= high + slack);
        }
    }

    #[test]
    fn macd_outputs_have_the_input_length_and_their_own_warm_up(
        (values, fast, slow, signal) in series_and_macd_parameters()
    ) {
        let output = macd(&Series::new(values.clone()).unwrap(), fast, slow, signal).unwrap();
        let [line, signal_line, hist] = output.outputs() else {
            panic!("expected three outputs");
        };
        let line_start = fast.max(slow) - 1;
        let signal_start = line_start + signal - 1;

        for series in [line, signal_line, hist] {
            prop_assert_eq!(series.len(), values.len());
        }
        prop_assert!(line[..line_start].iter().all(|value| value.is_nan()));
        prop_assert!(line[line_start..].iter().all(|value| value.is_finite()));
        for series in [signal_line, hist] {
            prop_assert!(series[..signal_start].iter().all(|value| value.is_nan()));
            prop_assert!(series[signal_start..].iter().all(|value| value.is_finite()));
        }
    }

    #[test]
    fn macd_histogram_is_exactly_macd_minus_signal(
        (values, fast, slow, signal) in series_and_macd_parameters()
    ) {
        let output = macd(&Series::new(values).unwrap(), fast, slow, signal).unwrap();
        let [line, signal_line, hist] = output.outputs() else {
            panic!("expected three outputs");
        };

        for index in 0..line.len() {
            if signal_line[index].is_nan() {
                prop_assert!(hist[index].is_nan());
            } else {
                prop_assert_eq!(hist[index], line[index] - signal_line[index]);
            }
        }
    }

    #[test]
    fn macd_of_constant_input_is_zero(
        value in -1.0e6..1.0e6_f64,
        fast in 2_usize..30,
        slow in 2_usize..30,
        signal in 1_usize..15,
        extra in 0_usize..50,
    ) {
        let length = fast.max(slow) + signal - 1 + extra;
        let output = macd(&Series::new(vec![value; length]).unwrap(), fast, slow, signal).unwrap();
        // The SMA seeds of a constant may differ from it by rounding.
        let tolerance = 1.0e-9 * value.abs().max(1.0);

        for series in output.outputs() {
            for result in series.iter().filter(|result| !result.is_nan()) {
                prop_assert!(result.abs() <= tolerance, "{} is not 0", result);
            }
        }
    }
}

/// TA-Lib's EMA of `values`, seeded at `start` with the simple average of the
/// `period` values ending there, as one plain pass: the reference the fused
/// MACD kernel must match bit for bit.
fn ema_pass(values: &[f64], period: usize, start: usize) -> Vec<f64> {
    let k = 2.0 / (period + 1) as f64;
    let mut output = vec![f64::NAN; values.len()];
    let mut previous = values[start + 1 - period..=start].iter().sum::<f64>() / period as f64;
    output[start] = previous;
    for index in start + 1..values.len() {
        previous = (values[index] - previous) * k + previous;
        output[index] = previous;
    }
    output
}

/// MACD one pass at a time: slow EMA, fast EMA, their difference, the signal
/// EMA of that, then the histogram.
fn macd_by_passes(values: &[f64], fast: usize, slow: usize, signal: usize) -> [Vec<f64>; 3] {
    let (fast, slow) = (fast.min(slow), fast.max(slow));
    let macd_start = slow - 1;
    let signal_start = slow + signal - 2;

    let slow_ema = ema_pass(values, slow, macd_start);
    let fast_ema = ema_pass(values, fast, macd_start);
    let line: Vec<f64> = fast_ema.iter().zip(&slow_ema).map(|(f, s)| f - s).collect();
    let signal_line = ema_pass(&line, signal, signal_start);
    let histogram = line
        .iter()
        .zip(&signal_line)
        .enumerate()
        .map(|(index, (m, s))| {
            if index < signal_start {
                f64::NAN
            } else {
                m - s
            }
        })
        .collect();

    [line, signal_line, histogram]
}

/// Bit-for-bit equality (`NaN` equal to `NaN`, `0.0` not equal to `-0.0`).
fn assert_bits_equal(actual: &[f64], expected: &[f64], what: &str) {
    assert_eq!(actual.len(), expected.len(), "{what}: length");
    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a.is_nan() && e.is_nan()) || a.to_bits() == e.to_bits(),
            "{what}, index {index}: {a:e} != {e:e}"
        );
    }
}

fn assert_macd_matches_passes(values: &[f64], fast: usize, slow: usize, signal: usize) {
    let output = macd(&Series::new(values.to_vec()).unwrap(), fast, slow, signal).unwrap();
    let expected = macd_by_passes(values, fast, slow, signal);

    for ((actual, expected), what) in
        output
            .outputs()
            .iter()
            .zip(&expected)
            .zip(["macd", "signal", "histogram"])
    {
        assert_bits_equal(actual, expected, what);
    }
}

proptest! {
    #[test]
    fn fused_macd_matches_one_pass_per_ema_bit_for_bit(
        (values, fast, slow, signal) in series_and_macd_parameters()
    ) {
        assert_macd_matches_passes(&values, fast, slow, signal);
        // The same parameters on the shortest input they accept.
        let required = fast.max(slow) + signal - 1;
        assert_macd_matches_passes(&values[..required], fast, slow, signal);
    }
}

#[test]
fn fused_macd_matches_one_pass_per_ema_on_edge_parameters() {
    let values: Vec<f64> = (0..120)
        .map(|i| (i as f64 * 0.37).sin() * 5.0 + 100.0 + i as f64 * 0.01)
        .collect();
    // Defaults, fast == slow, signal == 1, swapped, minimal periods.
    let cases = [
        (12, 26, 9),
        (5, 5, 3),
        (12, 26, 1),
        (26, 12, 9),
        (2, 2, 1),
        (2, 3, 1),
        (5, 35, 5),
    ];

    for (fast, slow, signal) in cases {
        let required = fast.max(slow) + signal - 1;
        assert_macd_matches_passes(&values, fast, slow, signal);
        assert_macd_matches_passes(&values[..required], fast, slow, signal);
    }
}

/// A deterministic random walk of `len` rows from `seed` (xorshift64 steps
/// of up to ±1 from a start of 100, so it may cross zero).
fn random_walk(seed: u64, len: usize) -> Vec<f64> {
    let mut state = seed | 1;
    let mut price = 100.0_f64;

    (0..len)
        .map(|_| {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            price += (state >> 11) as f64 / (1_u64 << 53) as f64 * 2.0 - 1.0;
            price
        })
        .collect()
}

/// The WMA of the window ending at `index`, summed directly.
fn direct_wma(values: &[f64], index: usize, period: usize) -> f64 {
    let window = &values[index + 1 - period..=index];
    let weighted: f64 = window
        .iter()
        .enumerate()
        .map(|(position, value)| value * (position + 1) as f64)
        .sum();

    weighted / (period * (period + 1) / 2) as f64
}

proptest! {
    #[test]
    fn wma_output_length_and_warm_up_are_exact((values, period) in series_and_period()) {
        let output = wma(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..period - 1].iter().all(|value| value.is_nan()));
        prop_assert!(output[period - 1..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn wma_lies_within_its_window((values, period) in series_and_period()) {
        let output = wma(&Series::new(values.clone()).unwrap(), period).unwrap();

        for (index, average) in output.values().iter().enumerate().skip(period - 1) {
            let window = &values[index + 1 - period..=index];
            let low = window.iter().copied().fold(f64::INFINITY, f64::min);
            let high = window.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            let slack = 1.0e-9 * high.abs().max(low.abs()).max(1.0);

            prop_assert!(
                *average >= low - slack && *average <= high + slack,
                "index {}: {} outside [{}, {}]", index, average, low, high
            );
        }
    }

    #[test]
    fn wma_of_constant_input_is_that_constant(
        value in -1.0e6..1.0e6_f64,
        length in 1_usize..300,
        period_seed in 0_usize..300,
    ) {
        let period = period_seed % length + 1;
        let output = wma(&Series::new(vec![value; length]).unwrap(), period).unwrap();

        for average in &output.values()[period - 1..] {
            prop_assert!((average - value).abs() <= 1.0e-12 * value.abs().max(1.0));
        }
    }
}

proptest! {
    // 100,000 rows checked window by window: a few cases are enough.
    #![proptest_config(ProptestConfig::with_cases(6))]

    #[test]
    fn wma_matches_a_direct_weighted_sum_on_long_random_walks(
        seed in any::<u64>(),
        period in 2_usize..200,
    ) {
        let values = random_walk(seed, 100_000);
        let output = wma(&Series::new(values.clone()).unwrap(), period).unwrap();

        for (index, average) in output.values().iter().enumerate().skip(period - 1) {
            let expected = direct_wma(&values, index, period);
            let window = &values[index + 1 - period..=index];
            let scale = window.iter().fold(0.0_f64, |most, value| most.max(value.abs()));

            prop_assert!(
                (average - expected).abs() <= 1.0e-9 * scale.max(1.0),
                "index {}: {} vs direct {}", index, average, expected
            );
        }
    }
}

/// A series of 1 to 300 prices and a period whose cascade of `depth` EMAs
/// fits it (`depth * (period - 1) + 1` rows).
fn series_and_cascade_period(depth: usize) -> impl Strategy<Value = (Vec<f64>, usize)> {
    prop::collection::vec(-1.0e6..1.0e6_f64, 1..300).prop_flat_map(move |values| {
        let longest = (values.len() - 1) / depth + 1;
        (Just(values), 1..=longest)
    })
}

/// The EMAs of a cascade, one `kernels::ema` pass each: the first over
/// `values`, each later one over the previous one's values from its first
/// value on, shifted back so every EMA is aligned with `values`.
fn ema_cascade(values: &[f64], period: usize, depth: usize) -> Vec<Vec<f64>> {
    let mut emas: Vec<Vec<f64>> = vec![kernels::ema(values, period)];
    for level in 1..depth {
        let offset = level * (period - 1);
        let mut aligned = vec![f64::NAN; offset];
        aligned.extend(kernels::ema(&emas[level - 1][offset..], period));
        emas.push(aligned);
    }
    emas
}

/// DEMA as one `kernels::ema` pass after another: `2 * EMA1 - EMA2`.
fn dema_by_passes(values: &[f64], period: usize) -> Vec<f64> {
    if period == 1 {
        return values.to_vec();
    }
    let emas = ema_cascade(values, period, 2);
    let start = 2 * (period - 1);

    (0..values.len())
        .map(|index| {
            if index < start {
                f64::NAN
            } else {
                2.0 * emas[0][index] - emas[1][index]
            }
        })
        .collect()
}

proptest! {
    #[test]
    fn fused_dema_matches_two_ema_passes_bit_for_bit(
        (values, period) in series_and_cascade_period(2)
    ) {
        let required = 2 * period - 1;
        for values in [&values[..], &values[..required]] {
            let output = dema(&Series::new(values.to_vec()).unwrap(), period).unwrap();
            assert_bits_equal(output.values(), &dema_by_passes(values, period), "dema");
        }
    }

    #[test]
    fn dema_output_length_and_warm_up_are_exact(
        (values, period) in series_and_cascade_period(2)
    ) {
        let output = dema(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();
        let start = 2 * (period - 1);

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..start].iter().all(|value| value.is_nan()));
        prop_assert!(output[start..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn dema_of_constant_input_is_that_constant(
        value in -1.0e6..1.0e6_f64,
        length in 1_usize..300,
        period_seed in 0_usize..300,
    ) {
        let period = period_seed % ((length - 1) / 2 + 1) + 1;
        let output = dema(&Series::new(vec![value; length]).unwrap(), period).unwrap();

        for average in &output.values()[2 * (period - 1)..] {
            prop_assert!((average - value).abs() <= 1.0e-9 * value.abs().max(1.0));
        }
    }
}

/// TEMA as one `kernels::ema` pass after another:
/// `EMA3 + (3 * EMA1 - 3 * EMA2)`, TA-Lib's order.
fn tema_by_passes(values: &[f64], period: usize) -> Vec<f64> {
    if period == 1 {
        return values.to_vec();
    }
    let emas = ema_cascade(values, period, 3);
    let start = 3 * (period - 1);

    (0..values.len())
        .map(|index| {
            if index < start {
                f64::NAN
            } else {
                emas[2][index] + (3.0 * emas[0][index] - 3.0 * emas[1][index])
            }
        })
        .collect()
}

proptest! {
    #[test]
    fn fused_tema_matches_three_ema_passes_bit_for_bit(
        (values, period) in series_and_cascade_period(3)
    ) {
        let required = 3 * period - 2;
        for values in [&values[..], &values[..required]] {
            let output = tema(&Series::new(values.to_vec()).unwrap(), period).unwrap();
            assert_bits_equal(output.values(), &tema_by_passes(values, period), "tema");
        }
    }

    #[test]
    fn tema_output_length_and_warm_up_are_exact(
        (values, period) in series_and_cascade_period(3)
    ) {
        let output = tema(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();
        let start = 3 * (period - 1);

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..start].iter().all(|value| value.is_nan()));
        prop_assert!(output[start..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn tema_of_constant_input_is_that_constant(
        value in -1.0e6..1.0e6_f64,
        length in 1_usize..300,
        period_seed in 0_usize..300,
    ) {
        let period = period_seed % ((length - 1) / 3 + 1) + 1;
        let output = tema(&Series::new(vec![value; length]).unwrap(), period).unwrap();

        for average in &output.values()[3 * (period - 1)..] {
            prop_assert!((average - value).abs() <= 1.0e-9 * value.abs().max(1.0));
        }
    }
}

/// A series of 2 to 300 prices in runs of repeated values (so flat windows
/// occur), and a period below its length.
fn series_with_flats_and_kama_period() -> impl Strategy<Value = (Vec<f64>, usize)> {
    prop::collection::vec((-1.0e6..1.0e6_f64, 1_usize..40), 2..40).prop_flat_map(|runs| {
        let mut values: Vec<f64> = runs
            .iter()
            .flat_map(|&(value, count)| std::iter::repeat_n(value, count))
            .take(300)
            .collect();
        if values.len() < 2 {
            values.push(values[0] + 1.0);
        }
        let longest = values.len() - 1;
        (Just(values), 1..=longest)
    })
}

proptest! {
    #[test]
    fn kama_output_length_and_warm_up_are_exact(
        (values, period) in series_with_flats_and_kama_period()
    ) {
        let output = kama(&Series::new(values.clone()).unwrap(), period).unwrap();
        let output = output.values();
        let start = if period == 1 { 0 } else { period };

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..start].iter().all(|value| value.is_nan()));
        prop_assert!(output[start..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn kama_stays_within_the_prices_since_its_seed(
        (values, period) in series_with_flats_and_kama_period()
    ) {
        // Each step moves part of the way to the price (SC is in (0, 1)), so
        // KAMA never leaves the range of the prices from its seed on.
        let output = kama(&Series::new(values.clone()).unwrap(), period).unwrap();
        let seed = period - 1;
        let mut low = values[seed];
        let mut high = values[seed];

        for (index, average) in output.values().iter().enumerate().skip(seed + 1) {
            low = low.min(values[index]);
            high = high.max(values[index]);
            let slack = 1.0e-9 * high.abs().max(low.abs()).max(1.0);

            prop_assert!(
                *average >= low - slack && *average <= high + slack,
                "index {}: {} outside [{}, {}]", index, average, low, high
            );
        }
    }
}

/// High, low and close columns of 4 to 300 rows (high at or above low,
/// close between them; some rows flat) and an ADX period that fits them.
fn ohlc_and_adx_period() -> impl Strategy<Value = ([Vec<f64>; 3], usize)> {
    let row = (
        -1.0e6..1.0e6_f64,
        prop_oneof![Just(0.0), 0.0..1.0e3_f64],
        0.0..=1.0_f64,
    );
    prop::collection::vec(row, 4..300).prop_flat_map(|rows| {
        let length = rows.len();
        let low: Vec<f64> = rows.iter().map(|(low, _, _)| *low).collect();
        let high: Vec<f64> = rows.iter().map(|(low, range, _)| low + range).collect();
        let close = rows
            .iter()
            .map(|(low, range, at)| low + range * at)
            .collect();
        (Just([high, low, close]), 2..=length / 2)
    })
}

proptest! {
    #[test]
    fn adx_outputs_and_warm_ups_are_exact((columns, period) in ohlc_and_adx_period()) {
        let [high, low, close] = columns.clone().map(|values| Series::new(values).unwrap());
        let output = adx(&high, &low, &close, period).unwrap();
        let starts = [2 * period - 1, period, period];

        prop_assert_eq!(output.output_count(), 3);
        for (line, start) in output.outputs().iter().zip(starts) {
            prop_assert_eq!(line.len(), columns[0].len());
            prop_assert!(line[..start].iter().all(|value| value.is_nan()));
            prop_assert!(line[start..].iter().all(|value| value.is_finite()));
        }
    }

    #[test]
    fn adx_lines_stay_between_0_and_100((columns, period) in ohlc_and_adx_period()) {
        // With the close inside each row's range, a row's +DM and -DM (only
        // one is non-zero) never exceed its true range, so the DIs and their
        // sum stay in [0, 100], and so do DX and ADX.
        let [high, low, close] = columns.map(|values| Series::new(values).unwrap());
        let output = adx(&high, &low, &close, period).unwrap();
        let [adx, plus_di, minus_di] = [0, 1, 2].map(|index| output.outputs()[index].clone());
        let slack = 1.0e-9;

        for value in adx.iter().chain(&plus_di).chain(&minus_di).filter(|v| !v.is_nan()) {
            prop_assert!(*value >= -slack && *value <= 100.0 + slack, "{} outside [0, 100]", value);
        }
        for (plus, minus) in plus_di.iter().zip(&minus_di).skip(period) {
            prop_assert!(plus + minus <= 100.0 + slack, "+DI {} and -DI {} sum above 100", plus, minus);
        }
    }
}

/// High and low columns of 2 to 300 rows (high at or above low; some rows
/// flat), with an acceleration at most its maximum.
fn high_low_and_sar_parameters() -> impl Strategy<Value = (Vec<f64>, Vec<f64>, f64, f64)> {
    let row = (-1.0e6..1.0e6_f64, prop_oneof![Just(0.0), 0.0..1.0e3_f64]);
    (
        prop::collection::vec(row, 2..300),
        1.0e-4..1.0_f64,
        1.0..4.0_f64,
    )
        .prop_map(|(rows, acceleration, ratio)| {
            let low = rows.iter().map(|(low, _)| *low).collect();
            let high = rows.iter().map(|(low, range)| low + range).collect();
            (high, low, acceleration, acceleration * ratio)
        })
}

proptest! {
    #[test]
    fn sar_has_exactly_one_warm_up_row((high, low, acceleration, maximum) in high_low_and_sar_parameters()) {
        let length = high.len();
        let output = sar(&Series::new(high).unwrap(), &Series::new(low).unwrap(), acceleration, maximum).unwrap();
        let values = output.values();

        prop_assert_eq!(output.output_count(), 1);
        prop_assert_eq!(values.len(), length);
        prop_assert!(values[0].is_nan());
        prop_assert!(values[1..].iter().all(|value| value.is_finite()));
    }

    #[test]
    fn sar_never_lies_inside_a_row_or_outside_the_series((high, low, acceleration, maximum) in high_low_and_sar_parameters()) {
        // A long SAR is written below the row's low and a short one above
        // its high; a reversal writes the old EP pushed out to the row's
        // extreme. Every SAR is a price seen so far or a step between two.
        let output = sar(&Series::new(high.clone()).unwrap(), &Series::new(low.clone()).unwrap(), acceleration, maximum).unwrap();
        let floor = low.iter().copied().fold(f64::INFINITY, f64::min);
        let ceiling = high.iter().copied().fold(f64::NEG_INFINITY, f64::max);

        for (index, value) in output.values().iter().enumerate().skip(1) {
            prop_assert!(*value <= low[index] || *value >= high[index], "row {}: {} inside [{}, {}]", index, value, low[index], high[index]);
            prop_assert!(*value >= floor && *value <= ceiling, "row {}: {} outside the series", index, value);
        }
    }
}

/// High and low columns of 3 to 300 rows (high at or above low; some rows
/// flat, some values repeated so ties occur) and a period that fits them.
fn high_low_and_aroon_period() -> impl Strategy<Value = (Vec<f64>, Vec<f64>, usize)> {
    let row = (
        prop_oneof![Just(0.0), Just(1.0), -1.0e6..1.0e6_f64],
        prop_oneof![Just(0.0), 0.0..1.0e3_f64],
    );
    prop::collection::vec(row, 3..300).prop_flat_map(|rows| {
        let low: Vec<f64> = rows.iter().map(|(low, _)| *low).collect();
        let high: Vec<f64> = rows.iter().map(|(low, range)| low + range).collect();
        let length = rows.len();
        (Just(high), Just(low), 2..length)
    })
}

proptest! {
    #[test]
    fn aroon_outputs_have_period_warm_up_rows((high, low, period) in high_low_and_aroon_period()) {
        let length = high.len();
        let output = aroon(&Series::new(high).unwrap(), &Series::new(low).unwrap(), period).unwrap();

        prop_assert_eq!(output.output_count(), 3);
        for values in output.outputs() {
            prop_assert_eq!(values.len(), length);
            prop_assert!(values[..period].iter().all(|value| value.is_nan()));
            prop_assert!(values[period..].iter().all(|value| value.is_finite()));
        }
    }

    #[test]
    fn aroon_lies_on_its_grid_and_osc_is_up_minus_down((high, low, period) in high_low_and_aroon_period()) {
        // Up and down are `100 / period` times a whole number of rows from
        // 0 to `period`, clamped to [0, 100] (period 11's
        // `(100 / period) * period` is 100.00000000000001 unclamped); the
        // oscillator is their difference to rounding, within [-100, 100].
        let output = aroon(&Series::new(high).unwrap(), &Series::new(low).unwrap(), period).unwrap();
        let [up, down, osc] = [0, 1, 2].map(|i| &output.outputs()[i]);
        let factor = 100.0 / period as f64;

        for row in period..up.len() {
            for value in [up[row], down[row]] {
                prop_assert!((0.0..=100.0).contains(&value), "row {}: {}", row, value);
                let steps = (value / factor).round();
                prop_assert!((value - factor * steps).abs() <= 1e-9, "row {}: {}", row, value);
            }
            prop_assert!((-100.0..=100.0).contains(&osc[row]), "row {}: {}", row, osc[row]);
            prop_assert!((osc[row] - (up[row] - down[row])).abs() <= 1e-9);
        }
    }
}

/// High, low and close columns of 1 to 300 rows (high at or above low,
/// close between them; some rows flat, some values repeated) and three
/// windows that fit them, in any order.
fn ohlc_and_ichimoku_windows() -> impl Strategy<Value = ([Vec<f64>; 3], [usize; 3])> {
    let row = (
        prop_oneof![Just(0.0), Just(1.0), -1.0e6..1.0e6_f64],
        prop_oneof![Just(0.0), 0.0..1.0e3_f64],
        0.0..=1.0_f64,
    );
    prop::collection::vec(row, 1..300).prop_flat_map(|rows| {
        let length = rows.len();
        let low: Vec<f64> = rows.iter().map(|(low, _, _)| *low).collect();
        let high: Vec<f64> = rows.iter().map(|(low, range, _)| low + range).collect();
        let close = rows
            .iter()
            .map(|(low, range, at)| low + range * at)
            .collect();
        (
            Just([high, low, close]),
            [1..=length, 1..=length, 1..=length],
        )
    })
}

proptest! {
    #[test]
    fn ichimoku_outputs_keep_their_own_warm_ups(
        ([high, low, close], [tenkan, kijun, senkou]) in ohlc_and_ichimoku_windows()
    ) {
        let length = close.len();
        let output = ichimoku(
            &Series::new(high).unwrap(),
            &Series::new(low).unwrap(),
            &Series::new(close).unwrap(),
            tenkan,
            kijun,
            senkou,
            false,
        )
        .unwrap();

        prop_assert_eq!(output.output_count(), 5);
        let firsts = [tenkan - 1, kijun - 1, tenkan.max(kijun) - 1, senkou - 1, 0];
        for (values, first) in output.outputs().iter().zip(firsts) {
            prop_assert_eq!(values.len(), length);
            prop_assert!(values[..first].iter().all(|value| value.is_nan()));
            prop_assert!(values[first..].iter().all(|value| value.is_finite()));
        }
    }

    #[test]
    fn ichimoku_lines_are_window_midpoints_within_the_range(
        ([high, low, close], [tenkan, kijun, senkou]) in ohlc_and_ichimoku_windows()
    ) {
        // Each midpoint is Donchian's middle line bit for bit, so between the
        // window's lowest low and highest high; senkou span A is the average
        // of the first two; the chikou span is close.
        let output = ichimoku(
            &Series::new(high.clone()).unwrap(),
            &Series::new(low.clone()).unwrap(),
            &Series::new(close.clone()).unwrap(),
            tenkan,
            kijun,
            senkou,
            false,
        )
        .unwrap();
        let [conversion, base, span_a, span_b, chikou] = [0, 1, 2, 3, 4].map(|i| &output.outputs()[i]);

        for (line, period) in [(conversion, tenkan), (base, kijun), (span_b, senkou)] {
            let upper = kernels::rolling_max(&high, period);
            let lower = kernels::rolling_min(&low, period);
            for row in period - 1..close.len() {
                prop_assert_eq!(line[row].to_bits(), ((upper[row] + lower[row]) / 2.0).to_bits());
                prop_assert!(lower[row] <= line[row] && line[row] <= upper[row]);
            }
        }
        for row in tenkan.max(kijun) - 1..close.len() {
            prop_assert_eq!(span_a[row].to_bits(), ((conversion[row] + base[row]) / 2.0).to_bits());
        }
        prop_assert_eq!(chikou, &close);
    }
}

proptest! {
    #[test]
    fn ichimoku_shift_moves_the_unshifted_lines_by_kijun(
        ([high, low, close], [tenkan, kijun, senkou]) in ohlc_and_ichimoku_windows()
    ) {
        // Bit for bit: spans move `kijun` rows later, the chikou span `kijun`
        // rows earlier, NaN where nothing moves in; tenkan and kijun stay.
        let run = |shift| {
            ichimoku(
                &Series::new(high.clone()).unwrap(),
                &Series::new(low.clone()).unwrap(),
                &Series::new(close.clone()).unwrap(),
                tenkan,
                kijun,
                senkou,
                shift,
            )
            .unwrap()
            .into_outputs()
        };
        let (plain, shifted) = (run(false), run(true));
        let length = close.len();
        let bits = |value: f64| if value.is_nan() { u64::MAX } else { value.to_bits() };

        for row in 0..length {
            for line in [0, 1] {
                prop_assert_eq!(bits(shifted[line][row]), bits(plain[line][row]));
            }
            let (ahead, behind) = (row.checked_sub(kijun), row + kijun);
            for line in [2, 3] {
                let expected = ahead.map_or(f64::NAN, |from| plain[line][from]);
                prop_assert_eq!(bits(shifted[line][row]), bits(expected));
            }
            let expected = if behind < length { close[behind] } else { f64::NAN };
            prop_assert_eq!(bits(shifted[4][row]), bits(expected));
        }
    }
}
