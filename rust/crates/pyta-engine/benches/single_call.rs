//! Cost of each stage of one indicator call, from the raw kernel up to the engine.

use std::hint::black_box;
use std::time::Duration;

use criterion::{BatchSize, BenchmarkId, Criterion, SamplingMode, criterion_group, criterion_main};
use pyta_common::{LARGE_INPUT_LEN, SINGLE_CALL_SIZES};
use pyta_core::{IndicatorOutput, PytaResult, Series};
use pyta_engine::{IndicatorKind, IndicatorRequest, execute_batch, execute_direct};
use pyta_momentum::rsi;
use pyta_trend::sma;
use tokio::runtime::Builder;

type Kernel = fn(&Series, usize) -> PytaResult<IndicatorOutput>;

/// Every indicator measured here: its label, engine kind, kernel, and period.
/// To benchmark a new indicator, add one line.
const INDICATORS: [(&str, IndicatorKind, Kernel, usize); 2] = [
    ("sma", IndicatorKind::Sma, sma, 20),
    ("rsi", IndicatorKind::Rsi, rsi, 14),
];

fn single_call(c: &mut Criterion) {
    // Engine log records go to stderr only when RUST_LOG asks for them (for
    // example RUST_LOG=pyta::planner=debug); otherwise logging stays off.
    let _ = env_logger::try_init();

    // Built once, like the OnceLock runtime in pyta-python.
    let runtime = Builder::new_multi_thread().enable_all().build().unwrap();

    for (label, kind, kernel, period) in INDICATORS {
        single_call_for(c, &runtime, label, kind, kernel, period);
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
) {
    let mut group = c.benchmark_group(format!("{label}_single"));

    for n in SINGLE_CALL_SIZES {
        let data: Vec<f64> = (0..n).map(|i| (i as f64).sin()).collect();
        let series = Series::new(data.clone()).unwrap();

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

        group.bench_with_input(BenchmarkId::new("kernel", n), &series, |b, s| {
            b.iter(|| kernel(black_box(s), period).unwrap());
        });

        group.bench_with_input(BenchmarkId::new("engine", n), &series, |b, s| {
            b.iter_batched(
                || IndicatorRequest::new(kind, s.clone(), period),
                |request| runtime.block_on(execute_batch(vec![request])),
                BatchSize::LargeInput,
            );
        });

        group.bench_with_input(BenchmarkId::new("direct", n), &series, |b, s| {
            let request = IndicatorRequest::new(kind, s.clone(), period);
            b.iter(|| execute_direct(black_box(&request)).unwrap());
        });
    }

    group.finish();
}

criterion_group!(benches, single_call);
criterion_main!(benches);
