#!/usr/bin/env bash
# Mock service probe used by the rollup harness (stands in for real probes).
#
# Usage: mock_probe.sh <variant> [value]
#
# Variants:
#   ok-marker    prints progress lines, then a "READY <value>" result line,
#                exits 0 (value defaults to green-42 if not given)
#   ok-empty     prints progress lines but has no result to report, exits 0
#   fail-exit-3  prints progress lines, reports an error on stderr, exits 3
set -u

variant="${1:-}"
value="${2:-green-42}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Record that this probe was actually invoked (harness bookkeeping).
touch "$here/.invoked-$variant"

case "$variant" in
  ok-marker)
    echo "probing service ..."
    echo "collecting metrics ..."
    echo "READY $value"
    ;;
  ok-empty)
    echo "probing service ..."
    echo "nothing to report"
    ;;
  fail-exit-3)
    echo "probing service ..."
    echo "mock_probe: backend refused the health query" >&2
    exit 3
    ;;
  *)
    echo "mock_probe: unknown variant '$variant'" >&2
    exit 2
    ;;
esac
