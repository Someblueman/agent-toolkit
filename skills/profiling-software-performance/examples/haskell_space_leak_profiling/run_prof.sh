#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "1. Compiling Haskell Application with GHC Profiling..."
echo "========================================================"
ghc -O2 -prof -fprof-auto -rtsopts SpaceLeakDemo.hs -o SpaceLeakDemo

echo -e "\n========================================================"
echo "2. Running Executable with Time Profiling & GC Stats (+RTS -p -s)..."
echo "========================================================"
./SpaceLeakDemo 1000000 +RTS -p -s -RTS

echo -e "\n========================================================"
echo "3. Analyzing Generated GHC Profile (.prof)..."
echo "========================================================"
python3 "$SCRIPT_DIR/../../scripts/analyze_ghc_prof.py" SpaceLeakDemo.prof

echo -e "\n[+] Haskell space leak profiling demo completed successfully."
