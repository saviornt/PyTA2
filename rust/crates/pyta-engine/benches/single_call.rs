use std::hint::black_box;

use criterion::{BatchSize, BenchmarkId, Criterion, criterion_group, criterion_main};
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
        let series = Series::new(data).unwrap();

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
