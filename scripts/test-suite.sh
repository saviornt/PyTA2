#!/usr/bin/env bash
set -euo pipefail

# Resolve the project root from this script's location.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

clear
echo "<==> Running PyTA test suite <==>"
echo

echo "==> Checking Rust formatting..."
cargo fmt --all -- --check
echo

echo "==> Running Clippy on Rust workspace..."
cargo clippy --workspace --all-targets --all-features -- -D warnings
echo

echo "==> Testing Rust workspace..."
cargo test --workspace
echo

echo "==> Building the Python extension..."
uv run --with maturin maturin develop \
    --manifest-path rust/crates/pyta-python/Cargo.toml
echo

echo "==> Running Python tests..."
uv run --extra pandas pytest
echo

echo "==> Running Python Ruff tests..."
uv run ruff check python tests
echo

echo "==> Running Python Ruff format tests..."
uv run ruff format --check python tests
echo

echo "==> Testing suite completed."