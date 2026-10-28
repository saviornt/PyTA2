//! Cost of each stage of one indicator call, from the raw kernel up to the engine.

use std::hint::black_box;
use std::time::Duration;

use criterion::{BatchSize, BenchmarkId, Criterion, SamplingMode, criterion_group, criterion_main};
use pyta_common::{LARGE_INPUT_LEN, SINGLE_CALL_SIZES};
use pyta_core::{Columns, IndicatorOutput, PytaResult, Series};
use pyta_engine::{IndicatorKind, IndicatorRequest, execute_batch, execute_direct};
use pyta_momentum::{cci, rsi};
use pyta_trend::sma;
use tokio::runtime::Builder;

/// A kernel called on its input columns, in slot order.
type Kernel = fn(&[Series], usize) -> PytaResult<IndicatorOutput>;

/// Every indicator measured here: its label, engine kind, kernel, period,
/// and number of input columns. To benchmark a new indicator, add one line.
const INDICATORS: [(&str, IndicatorKind, Kernel, usize, usize); 3] = [
    ("sma", IndicatorKind::Sma, |c, p| sma(&c[0], p), 20, 1),
    ("rsi", IndicatorKind::Rsi, |c, p| rsi(&c[0], p), 14, 1),
    (
        "cci",
        IndicatorKind::Cci,
        |c, p| cci(&c[0], &c[1], &c[2], p),
        14,
        3,
    ),
];

/// The input columns: a sine wave, offset upwards for each extra column, so
/// a multi-column indicator gets high, low and close in that order.
fn columns(n: usize, width: usize) -> Vec<Series> {
    (0..width)
        .map(|column| {
            let offset = (width - 1 - column) as f64 * 0.5;
            Series::new((0..n).map(|i| (i as f64).sin() + offset).collect()).unwrap()
        })
        .collect()
}

/// A request for `kind` on `columns`.
fn request(kind: IndicatorKind, columns: &[Series], period: usize) -> IndicatorRequest {
    match columns {
        [series] => IndicatorRequest::new(kind, series.clone(), period),
        _ => IndicatorRequest::with_columns(kind, Columns::new(columns.to_vec()).unwrap(), period),
    }
}

fn single_call(c: &mut Criterion) {
    // Engine log records go to stderr only when RUST_LOG asks for them (for
    // example RUST_LOG=pyta::planner=debug); otherwise logging stays off.
    let _ = env_logger::try_init();

    // Built once, like the OnceLock runtime in pyta-python.
    let runtime = Builder::new_multi_thread().enable_all().build().unwrap();

    for (label, kind, kernel, period, width) in INDICATORS {
        single_call_for(c, &runtime, label, kind, kernel, period, width);
    }
}

/// Measures one indicator at every single-call size, from the raw kernel up
/// to the full engine path.
fn single_call_for(
    c: &mut Criterion,
    runtime: &tokio::runtime::Runtime,
    label: &str,
    kind: IndicatorKind,
    kernel: Kernel,
    period: usize,
    width: usize,
) {
    let mut group = c.benchmark_group(format!("{label}_single"));

    for n in SINGLE_CALL_SIZES {
        let input = columns(n, width);
        // The copy and validation stages measure one column.
        let data = input[0].values().to_vec();

        // Slow sizes: flat sampling and a longer window to avoid the 5s warning
        if n >= LARGE_INPUT_LEN {
            group.sampling_mode(SamplingMode::Flat);
            group.measurement_time(Duration::from_secs(10));
        } else {
            group.sampling_mode(SamplingMode::Auto);
            group.measurement_time(Duration::from_secs(5));
        }

        // Allocation + memcpy only: the baseline for `series_new`.
        group.bench_with_input(BenchmarkId::new("clone", n), &data, |b, d| {
            b.iter(|| black_box(d.clone()));
        });

        // Allocation + memcpy + validation scan.
        group.bench_with_input(BenchmarkId::new("series_new", n), &data, |b, d| {
            b.iter_batched(
                || d.clone(),
                |values| Series::new(values).unwrap(),
                BatchSize::LargeInput,
            );
        });

        // Fused copy + validation, as used at the Python boundary.
        group.bench_with_input(BenchmarkId::new("series_from_slice", n), &data, |b, d| {
            b.iter(|| Series::from_slice(black_box(d)).unwrap());
        });

        group.bench_with_input(BenchmarkId::new("kernel", n), &input, |b, s| {
            b.iter(|| kernel(black_box(s), period).unwrap());
        });

        group.bench_with_input(BenchmarkId::new("engine", n), &input, |b, s| {
            b.iter_batched(
                || request(kind, s, period),
                |request| runtime.block_on(execute_batch(vec![request])),
                BatchSize::LargeInput,
            );
        });

        group.bench_with_input(BenchmarkId::new("direct", n), &input, |b, s| {
            let request = request(kind, s, period);
            b.iter(|| execute_direct(black_box(&request)).unwrap());
        });
    }

    group.finish();
}

criterion_group!(benches, single_call);
criterion_main!(benches);
