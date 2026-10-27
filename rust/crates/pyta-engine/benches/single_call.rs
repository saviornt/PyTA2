use std::hint::black_box;
use std::time::Duration;

use criterion::{BatchSize, BenchmarkId, Criterion, criterion_group, criterion_main, SamplingMode};
use pyta_core::Series;
use pyta_engine::{IndicatorKind, IndicatorRequest, execute_batch, execute_direct};
use pyta_trend::sma;
use tokio::runtime::Builder;

fn single_call(c: &mut Criterion) {
    // Built once, like the OnceLock runtime in pyta-python.
    let runtime = Builder::new_multi_thread().enable_all().build().unwrap();
    let mut group = c.benchmark_group("sma_single");

    for n in [100, 1_000, 10_000, 100_000, 1_000_000] {
        let data: Vec<f64> = (0..n).map(|i| (i as f64).sin()).collect();
        let series = Series::new(data.clone()).unwrap();

        // Slow sizes: flat sampling and a longer window to avoid the 5s warning
        if n >= 1_000_000 {
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
            b.iter(|| sma(black_box(s), 20).unwrap());
        });

        group.bench_with_input(BenchmarkId::new("engine", n), &series, |b, s| {
            b.iter_batched(
                || IndicatorRequest::new(IndicatorKind::Sma, s.clone(), 20),
                |request| runtime.block_on(execute_batch(vec![request])),
                BatchSize::LargeInput,
            );
        });

        group.bench_with_input(BenchmarkId::new("direct", n), &series, |b, s| {
            let request = IndicatorRequest::new(IndicatorKind::Sma, s.clone(), 20);
            b.iter(|| execute_direct(black_box(&request)).unwrap());
        });
    }

    group.finish();
}

criterion_group!(benches, single_call);
criterion_main!(benches);
