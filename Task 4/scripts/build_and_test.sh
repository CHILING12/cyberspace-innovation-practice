#!/usr/bin/env bash
# Build + test on Linux ARM64 or x86_64. Run from repo root or any cwd.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BUILD_DIR="${BUILD_DIR:-build}"
cmake -S . -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR" -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"

echo
echo "=== test_vectors ==="
"$BUILD_DIR/test_vectors"
echo "=== test_impl ==="
"$BUILD_DIR/test_impl"
echo "=== test_random ==="
"$BUILD_DIR/test_random"
echo
echo "ALL TESTS PASSED"
echo "Optional: $BUILD_DIR/bench_sm3"
