//! Rolling highest and lowest values, with the row each was found on.

/// Calls `visit(row, index)` for every window of `period` values ending at
/// `row` (the current row included, as TA-Lib's `MAX` and `AROON`), with
/// `index` the row of the window's highest value. Ties go to the most recent
/// row, as TA-Lib's Aroon (`>=`) does.
///
/// Rows are visited in order, from `period - 1`. It runs in O(n) whatever
/// the period and the data, with the van Herk/Gil-Werman algorithm: see
/// [`for_each_window_extreme`] for how, and why not a monotonic deque.
///
/// The caller guarantees `1 <= period <= values.len()` and that `values`
/// holds no `NaN`.
pub fn for_each_window_max(values: &[f64], period: usize, visit: impl FnMut(usize, usize)) {
    for_each_window_extreme(values, period, visit, |value, other| value > other);
}

/// Calls `visit(row, index)` for every window of `period` values ending at
/// `row`, with `index` the row of the window's lowest value; ties go to the
/// most recent row (TA-Lib's Aroon, `<=`). See [`for_each_window_max`].
pub fn for_each_window_min(values: &[f64], period: usize, visit: impl FnMut(usize, usize)) {
    for_each_window_extreme(values, period, visit, |value, other| value < other);
}

/// Calculates the highest value of each `period`-value window ending at each
/// row, with `NaN` in the first `period - 1` positions (Donchian, Williams
/// %R, Stochastic, Ichimoku).
///
/// The caller guarantees `1 <= period <= values.len()`.
#[must_use]
pub fn rolling_max(values: &[f64], period: usize) -> Vec<f64> {
    let mut output = vec![f64::NAN; values.len()];
    for_each_window_max(values, period, |row, index| output[row] = values[index]);
    output
}

/// Calculates the lowest value of each `period`-value window ending at each
/// row, with `NaN` in the first `period - 1` positions.
///
/// The caller guarantees `1 <= period <= values.len()`.
#[must_use]
pub fn rolling_min(values: &[f64], period: usize) -> Vec<f64> {
    let mut output = vec![f64::NAN; values.len()];
    for_each_window_min(values, period, |row, index| output[row] = values[index]);
    output
}

/// The shared walk; `beats(value, other)` is true when `value` is strictly
/// more extreme than `other`.
///
/// The rows are cut into blocks of `period`, so a window ending in one block
/// starts in the block before (or at this block's start). Its extreme is the
/// better of the previous block's suffix extreme from the window's first row
/// (computed once per block, scanning backwards) and the current block's
/// prefix extreme up to the window's last row (a running value): about three
/// comparisons per row, each a select on values held in registers, so the
/// branch predictor plays no part and no data shape is slow. Ties go to the
/// later row throughout: the prefix replaces on equal, the suffix (scanned
/// backwards) only on strictly better, and the prefix, always the later of
/// the two, wins an equal comparison.
///
/// Measured against the alternatives on 1,000,000 rows of the maximum's row
/// (a throwaway program timing each with `Instant`, best of 9, release
/// build, i9-9900K on the `performance` governor, 2026-10-29; every result
/// checked equal to the rescan's, ties included), in ms for period 14 / 200:
///
/// | Input        | This      | Deque (`VecDeque`) | TA-Lib's lazy rescan | Rescan every window |
/// |--------------|-----------|--------------------|----------------------|---------------------|
/// | Random walk  | 3.1 / 2.6 | 13.2 / 12.0        | 4.9 / 6.2            | 34.2 / 224.3        |
/// | Rising       | 2.5 / 2.5 | 3.9 / 3.9          | 1.8 / 1.8            | 15.0 / 217.1        |
/// | Falling      | 2.6 / 2.6 | 3.8 / 3.8          | 7.4 / 95.1           | 12.4 / 173.1        |
///
/// The deque mispredicts its pop loop on price-like data; the lazy rescan
/// (rescan only when the extreme leaves the window) is O(n·period) when the
/// extreme leaves every row (a falling series for the maximum).
#[inline]
fn for_each_window_extreme(
    values: &[f64],
    period: usize,
    mut visit: impl FnMut(usize, usize),
    beats: impl Fn(f64, f64) -> bool,
) {
    debug_assert!(period >= 1 && period <= values.len());

    // The previous block's suffix extremes: entry `j` is the extreme of the
    // block's rows `j..period`, its row and its value.
    let mut suffix_index = vec![0_usize; period];
    let mut suffix_value = vec![0.0_f64; period];
    let mut block_start = 0;

    while block_start < values.len() {
        let block_end = (block_start + period).min(values.len());
        let block = &values[block_start..block_end];

        let (mut prefix_index, mut prefix_value) = (block_start, block[0]);
        for (row, &value) in (block_start..).zip(block) {
            // At least as extreme: the later row takes a tie.
            let replaces = !beats(prefix_value, value);
            prefix_index = if replaces { row } else { prefix_index };
            prefix_value = if replaces { value } else { prefix_value };

            if row + 1 >= period {
                let start = row + 1 - period;
                let index = if start >= block_start {
                    // The window is exactly this block.
                    prefix_index
                } else {
                    let slot = start + period - block_start;
                    if beats(suffix_value[slot], prefix_value) {
                        suffix_index[slot]
                    } else {
                        prefix_index
                    }
                };
                visit(row, index);
            }
        }

        // Only a full block is ever read back (the last may be partial).
        let (mut best_index, mut best_value) = (block_end - 1, block[block.len() - 1]);
        for (offset, &value) in block.iter().enumerate().rev() {
            // Strictly more extreme: the later row keeps a tie.
            let replaces = beats(value, best_value);
            best_index = if replaces {
                block_start + offset
            } else {
                best_index
            };
            best_value = if replaces { value } else { best_value };
            suffix_index[offset] = best_index;
            suffix_value[offset] = best_value;
        }

        block_start = block_end;
    }
}
