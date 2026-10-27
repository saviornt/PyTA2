//! Compares sequential direct execution against the concurrent batch engine.
//!
//! Each workload runs at several input sizes in two arms:
//! - `sequential`: calls `execute_direct` for each request in a loop.
//! - `batch`: submits all requests to `execute_batch` (Tokio + Rayon).
//!
//! Inputs are fully finite seeded random walks, because `Series::new`
//! rejects NaN and infinity.

use criterion::{BatchSize, BenchmarkId, Criterion, criterion_group, criterion_main};
use pyta_core::Series;
use pyta_engine::{
    IndicatorKind, IndicatorRequest, execute_batch, execute_direct, execute_sequential,
    should_parallelize,
};
use tokio::runtime::Builder;

const SIZES: [usize; 5] = [100, 1_000, 3_000, 10_000, 1_000_000];
const DS1_SEED: u64 = 0x9E37_79B9_7F4A_7C15;
const DS2_SEED: u64 = 0xD1B5_4A32_D192_ED03;

#[derive(Clone, Copy)]
enum Dataset {
    One,
    Two,
}

struct Workload {
    name: &'static str,
    jobs: &'static [(IndicatorKind, Dataset)],
}

const WORKLOADS: &[Workload] = &[
    Workload {
        name: "1_sma_ds1",
        jobs: &[(IndicatorKind::Sma, Dataset::One)],
    },
    Workload {
        name: "2_rsi_ds1",
        jobs: &[(IndicatorKind::Rsi, Dataset::One)],
    },
    Workload {
        name: "3_sma_rsi_ds1",
        jobs: &[
            (IndicatorKind::Sma, Dataset::One),
            (IndicatorKind::Rsi, Dataset::One),
        ],
    },
    Workload {
        name: "4_sma_sma_ds1_ds2",
        jobs: &[
            (IndicatorKind::Sma, Dataset::One),
            (IndicatorKind::Sma, Dataset::Two),
        ],
    },
    Workload {
        name: "5_rsi_rsi_ds1_ds2",
        jobs: &[
            (IndicatorKind::Rsi, Dataset::One),
            (IndicatorKind::Rsi, Dataset::Two),
        ],
    },
    Workload {
        name: "6_sma_rsi_ds1_ds2",
        jobs: &[
            (IndicatorKind::Sma, Dataset::One),
            (IndicatorKind::Rsi, Dataset::One),
            (IndicatorKind::Sma, Dataset::Two),
            (IndicatorKind::Rsi, Dataset::Two),
        ],
    },
];

fn period(kind: IndicatorKind) -> usize {
    match kind {
        IndicatorKind::Sma => 20,
        IndicatorKind::Rsi => 14,
    }
}

/// Deterministic, finite, positive "closing prices" (xorshift64 random walk).
fn random_walk(seed: u64, len: usize) -> Series {
    let mut state = seed;
    let mut price = 100.0_f64;

    let values = (0..len)
        .map(|_| {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;

            let unit = (state >> 11) as f64 / (1_u64 << 53) as f64;
            price = (price + (unit - 0.5) * 2.0).max(1.0);
            price
        })
        .collect();

    Series::new(values).expect("generated prices are finite and non-empty")
}

fn build_requests(
    jobs: &[(IndicatorKind, Dataset)],
    one: &Series,
    two: &Series,
) -> Vec<IndicatorRequest> {
    jobs.iter()
        .map(|&(kind, dataset)| {
            let series = match dataset {
                Dataset::One => one,
                Dataset::Two => two,
            };

            IndicatorRequest::new(kind, series.clone(), period(kind))
        })
        .collect()
}

fn workloads(c: &mut Criterion) {
    let runtime = Builder::new_multi_thread()
        .enable_all()
        .build()
        .expect("failed to build Tokio runtime");

    let cores = std::thread::available_parallelism()
        .map(usize::from)
        .unwrap_or(1);
    eprintln!("available_parallelism = {cores}");

    for workload in WORKLOADS {
        let mut group = c.benchmark_group(workload.name);

        for size in SIZES {
            group.sample_size(if size >= 1_000_000 { 20 } else { 100 });

            let ds1 = random_walk(DS1_SEED, size);
            let ds2 = random_walk(DS2_SEED, size);
            let requests = build_requests(workload.jobs, &ds1, &ds2);

            // Outputs are dropped outside the timed section in both arms.
            group.bench_function(BenchmarkId::new("sequential", size), |b| {
                b.iter_with_large_drop(|| {
                    requests
                        .iter()
                        .map(|request| execute_direct(request).unwrap())
                        .collect::<Vec<_>>()
                });
            });

            group.bench_function(BenchmarkId::new("batch", size), |b| {
                b.iter_batched(
                    || requests.clone(),
                    |batch| runtime.block_on(execute_batch(batch)),
                    BatchSize::LargeInput,
                );
            });

            group.bench_function(BenchmarkId::new("auto", size), |b| {
                b.iter_batched(
                    || requests.clone(),
                    |batch| {
                        if should_parallelize(&batch) {
                            runtime.block_on(execute_batch(batch))
                        } else {
                            execute_sequential(&batch)
                        }
                    },
                    BatchSize::LargeInput,
                );
            });
        }

        group.finish();
    }
}

criterion_group!(benches, workloads);
criterion_main!(benches);
