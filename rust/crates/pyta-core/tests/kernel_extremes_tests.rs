//! Rolling highest and lowest values and the rows they come from.

use pyta_core::kernels::{for_each_window_max, for_each_window_min, rolling_max, rolling_min};

fn max_indices(values: &[f64], period: usize) -> Vec<(usize, usize)> {
    let mut visits = Vec::new();
    for_each_window_max(values, period, |row, index| visits.push((row, index)));
    visits
}

fn min_indices(values: &[f64], period: usize) -> Vec<(usize, usize)> {
    let mut visits = Vec::new();
    for_each_window_min(values, period, |row, index| visits.push((row, index)));
    visits
}

const VALUES: [f64; 6] = [1.0, 3.0, 2.0, 3.0, 1.0, 0.0];

#[test]
fn highest_value_and_its_row_with_ties_to_the_most_recent() {
    // Windows of 3 ending at rows 2..=5: [1,3,2] [3,2,3] [2,3,1] [3,1,0].
    assert_eq!(max_indices(&VALUES, 3), [(2, 1), (3, 3), (4, 3), (5, 3)]);
    let output = rolling_max(&VALUES, 3);
    assert!(output[..2].iter().all(|value| value.is_nan()));
    assert_eq!(output[2..], [3.0, 3.0, 3.0, 3.0]);
}

#[test]
fn lowest_value_and_its_row() {
    assert_eq!(min_indices(&VALUES, 3), [(2, 0), (3, 2), (4, 4), (5, 5)]);
    let output = rolling_min(&VALUES, 3);
    assert!(output[..2].iter().all(|value| value.is_nan()));
    assert_eq!(output[2..], [1.0, 2.0, 1.0, 0.0]);
}

#[test]
fn lowest_ties_go_to_the_most_recent_row() {
    assert_eq!(min_indices(&[2.0, 1.0, 1.0, 5.0], 3), [(2, 2), (3, 2)]);
}

#[test]
fn an_extreme_leaves_with_its_row() {
    // The 9 at row 0 is the highest until its window ends.
    assert_eq!(
        max_indices(&[9.0, 1.0, 2.0, 0.0], 2),
        [(1, 0), (2, 2), (3, 2)]
    );
}

#[test]
fn period_one_is_each_row_itself() {
    let expected: Vec<(usize, usize)> = (0..6).map(|row| (row, row)).collect();
    assert_eq!(max_indices(&VALUES, 1), expected);
    assert_eq!(min_indices(&VALUES, 1), expected);
    assert_eq!(rolling_max(&VALUES, 1), VALUES);
}

#[test]
fn period_equal_to_the_length_gives_one_window() {
    assert_eq!(max_indices(&VALUES, 6), [(5, 3)]);
    assert_eq!(min_indices(&VALUES, 6), [(5, 5)]);
}

#[test]
fn flat_input_points_at_the_current_row() {
    let flat = [4.0; 5];
    assert_eq!(max_indices(&flat, 3), [(2, 2), (3, 3), (4, 4)]);
    assert_eq!(min_indices(&flat, 3), [(2, 2), (3, 3), (4, 4)]);
}
