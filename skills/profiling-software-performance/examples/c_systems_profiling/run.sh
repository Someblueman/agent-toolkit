#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[*] Compiling C Matrix Traversal Benchmark..."
clang -O2 -Wall -Wextra -g -fno-omit-frame-pointer -o matrix_traversal_benchmark matrix_traversal_benchmark.c

echo "[*] Running Benchmark..."
./matrix_traversal_benchmark
