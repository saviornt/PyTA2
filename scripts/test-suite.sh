#!/usr/bin/env bash
set -euo pipefail

# Resolve the project root from this script's location.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

clear
echo "==> Running PyTA test suite..."
echo ""
echo "==> Testing Rust workspace..."
cargo test --workspace
echo ""
echo "==> Running Clippy on Rust workspace..."
cargo clippy --workspace --all-targets --all-features -- -D warnings
echo ""