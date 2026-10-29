//! The shared rate-of-change kernel: TA-Lib's expression, the zero base and
//! the output offset.

use proptest::prelude::*;
use pyta_core::kernels::{rate_of_change, rate_of_change_into};

#[test]
fn rate_of_change_is_the_percentage_change_from_period_rows_earlier() {
    let output = rate_of_change(&[10.0, 20.0, 11.0, 30.0, 5.5], 2);

    assert!(output[..2].iter().all(|value| value.is_nan()));
    assert_eq!(
        output[2..],
        [
            (11.0 / 10.0 - 1.0) * 100.0,
            (30.0 / 20.0 - 1.0) * 100.0,
            (5.5 / 11.0 - 1.0) * 100.0,
        ]
    );
}

#[test]
fn a_zero_base_gives_zero_whatever_the_current_value() {
    // TA-Lib writes 0 rather than an infinity or NaN; only an exact 0.0
    // counts, so a tiny base still divides.
    let output = rate_of_change(&[0.0, -0.0, 1e-300, 5.0, -5.0, 2e-300], 3);

    assert_eq!(output[3..], [0.0, 0.0, (2e-300 / 1e-300 - 1.0) * 100.0]);
}

#[test]
fn rate_of_change_into_writes_only_the_values_after_the_warm_up() {
    let values = [4.0, 5.0, 6.0, 8.0];
    let mut output = [f64::NAN; 3];

    rate_of_change_into(&values, 1, &mut output);

    // TA-Lib's expression, rounding included: 6 / 5 - 1 is not exactly 0.2.
    assert_eq!(
        output,
        [
            (5.0 / 4.0 - 1.0) * 100.0,
            (6.0 / 5.0 - 1.0) * 100.0,
            (8.0 / 6.0 - 1.0) * 100.0,
        ]
    );
}

#[test]
fn a_falling_to_zero_series_reads_minus_100() {
    assert_eq!(rate_of_change(&[7.0, 0.0], 1)[1], -100.0);
}

proptest! {
    #[test]
    fn rate_of_change_matches_talib_loop_bit_for_bit(
        values in prop::collection::vec(prop_oneof![4 => -1.0e6..1.0e6_f64, 1 => Just(0.0)], 2..300),
        period_seed in 0_usize..300,
    ) {
        let period = period_seed % (values.len() - 1) + 1;
        let output = rate_of_change(&values, period);

        prop_assert_eq!(output.len(), values.len());
        prop_assert!(output[..period].iter().all(|value| value.is_nan()));
        for row in period..values.len() {
            let earlier = values[row - period];
            let expected = if earlier == 0.0 {
                0.0
            } else {
                (values[row] / earlier - 1.0) * 100.0
            };
            prop_assert_eq!(output[row].to_bits(), expected.to_bits(), "row {}", row);
        }
    }
}
