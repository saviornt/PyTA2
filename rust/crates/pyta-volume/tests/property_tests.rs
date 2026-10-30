//! OBV invariants that must hold for any valid input.

use proptest::prelude::*;
use pyta_core::Series;
use pyta_volume::obv;

/// Close and whole-number volume columns of 1 to 300 rows, some closes
/// repeating the previous one and some volumes zero.
fn close_and_volume() -> impl Strategy<Value = (Vec<f64>, Vec<f64>)> {
    let row = (
        prop_oneof![4 => 1.0..1.0e4_f64, 1 => Just(f64::NAN)],
        prop_oneof![4 => 0_u32..1_000_000_000, 1 => Just(0)],
    );
    prop::collection::vec(row, 1..300).prop_map(|rows| {
        let mut close: Vec<f64> = Vec::with_capacity(rows.len());
        for &(price, _) in &rows {
            // NaN means "repeat the previous close".
            let price = match close.last() {
                Some(&previous) if price.is_nan() => previous,
                _ if price.is_nan() => 100.0,
                _ => price,
            };
            close.push(price);
        }
        let volume = rows.iter().map(|&(_, size)| f64::from(size)).collect();
        (close, volume)
    })
}

fn obv_of(close: &[f64], volume: &[f64]) -> Vec<f64> {
    obv(
        &Series::new(close.to_vec()).unwrap(),
        &Series::new(volume.to_vec()).unwrap(),
    )
    .unwrap()
    .into_values()
}

proptest! {
    #[test]
    fn obv_has_no_warm_up_and_steps_by_the_volume((close, volume) in close_and_volume()) {
        let output = obv_of(&close, &volume);

        prop_assert_eq!(output.len(), close.len());
        prop_assert_eq!(output[0], volume[0]);
        for row in 1..close.len() {
            // Whole volumes below 2^53 in total: every step is exact.
            let step = output[row] - output[row - 1];
            let expected = if close[row] > close[row - 1] {
                volume[row]
            } else if close[row] < close[row - 1] {
                -volume[row]
            } else {
                0.0
            };
            prop_assert_eq!(step, expected, "row {}", row);
        }
    }
}
