//! Compares sequential execution against the parallel batch engine.
//!
//! Each workload runs at several input sizes in four arms:
//! - `sequential`: `execute_sequential`, the function `auto` uses when it stays sequential.
//! - `parallel`: `execute_parallel` (Rayon), the function `auto` uses for parallel work.
//! - `batch`: `execute_batch`, the async front door that hands the batch to Rayon in one hop.
//! - `auto`: the planner's choice between `sequential` and `parallel`.
//!
//! `few_requests` covers 3 to 10 requests and `many_datasets` 10 to 1,000, where the
//! planner's choice matters most.
//!
//! Inputs are fully finite seeded random walks, because `Series::new`
//! rejects NaN and infinity.

use criterion::{BatchSize, BenchmarkId, Criterion, SamplingMode, criterion_group, criterion_main};
use pyta_common::{
    FEW_REQUEST_COUNTS, FEW_REQUEST_SIZES, LARGE_INPUT_LEN, LARGE_SAMPLE_SIZE, MANY_DATASET_COUNTS,
    MANY_DATASET_SIZES, SAMPLE_SIZE, WORKLOAD_SIZES,
};
use pyta_core::Series;
use pyta_engine::{
    IndicatorKind, IndicatorRequest, execute_batch, execute_parallel, execute_sequential,
    should_parallelize,
};
use tokio::runtime::Builder;

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

        for size in WORKLOAD_SIZES {
            group.sample_size(if size >= LARGE_INPUT_LEN {
                LARGE_SAMPLE_SIZE
            } else {
                SAMPLE_SIZE
            });

            let ds1 = random_walk(DS1_SEED, size);
            let ds2 = random_walk(DS2_SEED, size);
            let requests = build_requests(workload.jobs, &ds1, &ds2);

            // All three arms use the same harness so they differ only in the
            // strategy under test: each iteration gets a fresh clone of the
            // requests (made outside the timed section), and results, and the
            // requests when the strategy borrows them, are returned so Criterion
            // drops them outside the timed section. A `sequential` arm built
            // on `iter_with_large_drop` instead kept every output alive for the
            // whole sample, which made it look 10-15% slower than identical code.
            group.bench_function(BenchmarkId::new("sequential", size), |b| {
                b.iter_batched(
                    || requests.clone(),
                    |batch| {
                        let results = execute_sequential(&batch);
                        (batch, results)
                    },
                    BatchSize::LargeInput,
                );
            });

            group.bench_function(BenchmarkId::new("parallel", size), |b| {
                b.iter_batched(
                    || requests.clone(),
                    |batch| {
                        let results = execute_parallel(&batch);
                        (batch, results)
                    },
                    BatchSize::LargeInput,
                );
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
                        let results = if should_parallelize(&batch, rayon::current_num_threads()) {
                            execute_parallel(&batch)
                        } else {
                            execute_sequential(&batch)
                        };
                        (batch, results)
                    },
                    BatchSize::LargeInput,
                );
            });
        }

        group.finish();
    }
}

/// One indicator over many datasets, comparing every way of running a batch.
///
/// Groups are named `many_<indicator>_x<count>` and sized by points per
/// dataset. Arms:
/// - `sequential`, `parallel`, `batch`, `auto`: as in `workloads`.
fn many_datasets(c: &mut Criterion) {
    let runtime = Builder::new_multi_thread()
        .enable_all()
        .build()
        .expect("failed to build Tokio runtime");

    for (kind, label) in [(IndicatorKind::Sma, "sma"), (IndicatorKind::Rsi, "rsi")] {
        for count in MANY_DATASET_COUNTS {
            let mut group = c.benchmark_group(format!("many_{label}_x{count}"));

            for size in MANY_DATASET_SIZES {
                if count * size >= LARGE_INPUT_LEN {
                    group.sample_size(LARGE_SAMPLE_SIZE);
                    group.sampling_mode(SamplingMode::Flat);
                } else {
                    group.sample_size(SAMPLE_SIZE);
                    group.sampling_mode(SamplingMode::Auto);
                }

                let requests: Vec<IndicatorRequest> = (0..count)
                    .map(|i| {
                        let series = random_walk(DS1_SEED.wrapping_add(i as u64), size);
                        IndicatorRequest::new(kind, series, period(kind))
                    })
                    .collect();

                // Same harness for every arm: see `workloads`.
                group.bench_function(BenchmarkId::new("sequential", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results = execute_sequential(&batch);
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
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
                            let results =
                                if should_parallelize(&batch, rayon::current_num_threads()) {
                                    execute_parallel(&batch)
                                } else {
                                    execute_sequential(&batch)
                                };
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });

                group.bench_function(BenchmarkId::new("parallel", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results = execute_parallel(&batch);
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });
            }

            group.finish();
        }
    }
}

/// A handful of requests (3 to 10), where the planner's choice is closest.
///
/// Groups are named `few_<indicators>_x<count>` and sized by points per
/// request; `sma_rsi` alternates the two indicators. Arms are `sequential`,
/// `parallel` and `auto`: `batch` only adds a fixed async hop.
fn few_requests(c: &mut Criterion) {
    let mixes: [(&str, &[IndicatorKind]); 3] = [
        ("sma", &[IndicatorKind::Sma]),
        ("rsi", &[IndicatorKind::Rsi]),
        ("sma_rsi", &[IndicatorKind::Sma, IndicatorKind::Rsi]),
    ];

    for (label, kinds) in mixes {
        for count in FEW_REQUEST_COUNTS {
            let mut group = c.benchmark_group(format!("few_{label}_x{count}"));
            group.sample_size(SAMPLE_SIZE);

            for size in FEW_REQUEST_SIZES {
                let requests: Vec<IndicatorRequest> = (0..count)
                    .map(|i| {
                        let kind = kinds[i % kinds.len()];
                        let series = random_walk(DS1_SEED.wrapping_add(i as u64), size);
                        IndicatorRequest::new(kind, series, period(kind))
                    })
                    .collect();

                // Same harness for every arm: see `workloads`.
                group.bench_function(BenchmarkId::new("sequential", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results = execute_sequential(&batch);
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });

                group.bench_function(BenchmarkId::new("parallel", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results = execute_parallel(&batch);
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });

                group.bench_function(BenchmarkId::new("auto", size), |b| {
                    b.iter_batched(
                        || requests.clone(),
                        |batch| {
                            let results =
                                if should_parallelize(&batch, rayon::current_num_threads()) {
                                    execute_parallel(&batch)
                                } else {
                                    execute_sequential(&batch)
                                };
                            (batch, results)
                        },
                        BatchSize::LargeInput,
                    );
                });
            }

            group.finish();
        }
    }
}

criterion_group!(benches, workloads, many_datasets, few_requests);
criterion_main!(benches);
