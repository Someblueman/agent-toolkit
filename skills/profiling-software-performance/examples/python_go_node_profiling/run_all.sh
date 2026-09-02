#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "1. Running Python Managed Profiling Demo..."
echo "========================================================"
python3 python_bottleneck.py

echo -e "\n========================================================"
echo "2. Running Go Benchmarks & Escape Analysis..."
echo "========================================================"
go test -v -bench=. -benchmem

echo -e "\n[*] Running Go Escape Analysis Diagnostics:"
go build -gcflags="-m" 2>&1 | grep -E "(escapes to heap|moved to heap)" || true

echo -e "\n========================================================"
echo "3. Running Node.js Profiling Demo..."
echo "========================================================"
node node_bottleneck.js

echo -e "\n[+] All Managed Runtime profiling demos executed successfully."
