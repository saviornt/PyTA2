
#!/usr/bin/env bash
set -euo pipefail

# Resolve the project root from this script's location.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==> Rebuilding and installing PyTA's Rust extension..."

uv run --with maturin maturin develop \
    --manifest-path rust/crates/pyta-python/Cargo.toml

echo
echo "==> Running PyTA smoke tests..."

uv run python tests/smoke/smoke_test.py

echo
echo "==> Build and smoke tests completed successfully."
