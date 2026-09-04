#!/usr/bin/env python3
"""
GHC Profiling Report Parser & Diagnostic Analyzer.

Parses Glasgow Haskell Compiler (GHC) runtime profiling reports (.prof),
extracting execution metadata, top cost-centre CPU consumers, nursery heap
allocators, and diagnosing space leaks or memory allocation hotspots.
"""

import argparse
import json
import re
import sys
from typing import Any


def parse_ghc_prof(prof_text: str) -> dict[str, Any]:
    """Parse GHC .prof file contents into structured metadata and cost-centre tables."""
    lines = prof_text.splitlines()

    metadata: dict[str, Any] = {
        "title": "",
        "command": "",
        "total_time_secs": 0.0,
        "total_ticks": 0,
        "tick_interval_us": 0,
        "cores": 1,
        "total_alloc_bytes": 0,
    }

    saw_time = saw_alloc = False
    # Extract header metadata
    for i, line in enumerate(lines[:30]):
        stripped = line.strip()
        if "Time and Allocation Profiling Report" in stripped:
            metadata["title"] = stripped
        elif "total time  =" in stripped:
            # Example: total time  =        1.42 secs   (1420 ticks @ 1000 us, 10 cores)
            match = re.search(
                r"total time\s*=\s*([\d\.]+)\s*secs\s*\((?:(\d+)\s*ticks)?(?:\s*@\s*(\d+)\s*us)?(?:,\s*(\d+)\s*cores)?\)",
                stripped,
            )
            if match:
                saw_time = True
                time_str, ticks_str, us_str, cores_str = match.groups()
                metadata["total_time_secs"] = float(time_str) if time_str else 0.0
                metadata["total_ticks"] = int(ticks_str) if ticks_str else 0
                metadata["tick_interval_us"] = int(us_str) if us_str else 1000
                metadata["cores"] = int(cores_str) if cores_str else 1
        elif "total alloc =" in stripped:
            # Example: total alloc = 852,120,448 bytes  (excludes profiling overheads)
            match = re.search(r"total alloc\s*=\s*([\d,]+)\s*bytes", stripped)
            if match:
                saw_alloc = True
                alloc_str = match.group(1).replace(",", "")
                metadata["total_alloc_bytes"] = int(alloc_str)

    # Find Top Cost Centres Summary Table
    # Header format: COST CENTRE          MODULE           SRC                       %time %alloc
    top_summary: list[dict[str, Any]] = []
    tree_nodes: list[dict[str, Any]] = []

    in_summary_table = False
    in_tree_table = False

    for line in lines:
        line_str = line.rstrip()
        if not line_str:
            continue

        # Check for summary section header
        if re.match(
            r"^COST CENTRE\s+MODULE\s+SRC\s+%time\s+%alloc\s*$", line_str.strip()
        ):
            in_summary_table = True
            in_tree_table = False
            continue

        # Check for hierarchical tree table header
        if "individual     inherited" in line_str:
            in_summary_table = False
            in_tree_table = False
            continue
        if re.match(
            r"^COST CENTRE\s+MODULE\s+SRC\s+no\.\s+entries\s+%time\s+%alloc\s+%time\s+%alloc\s*$",
            line_str.strip(),
        ):
            in_summary_table = False
            in_tree_table = True
            continue

        if in_summary_table:
            # Check for end of summary table
            if line_str.strip().startswith("COST CENTRE") or "individual" in line_str:
                in_summary_table = False
                continue

            # Format: <name> <module> <src> <%time> <%alloc>
            match = re.match(
                r"^\s*(\S+)\s+(\S+)\s+(.+?)\s+([\d\.]+)\s+([\d\.]+)\s*$",
                line_str,
            )
            if match:
                cc, mod, src, pct_time, pct_alloc = match.groups()
                top_summary.append(
                    {
                        "cost_centre": cc,
                        "module": mod,
                        "src": src.strip(),
                        "time_percent": float(pct_time),
                        "alloc_percent": float(pct_alloc),
                    }
                )

        elif in_tree_table:
            # Format with indentation indicating tree depth
            indent = len(line_str) - len(line_str.lstrip())
            match = re.match(
                r"^\s*(\S+)\s+(\S+)\s+(.+?)\s+(\d+)\s+(\d+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s*$",
                line_str,
            )
            if match:
                cc, mod, src, no_id, entries, ind_t, ind_a, inh_t, inh_a = (
                    match.groups()
                )
                tree_nodes.append(
                    {
                        "depth": indent,
                        "cost_centre": cc,
                        "module": mod,
                        "src": src.strip(),
                        "id": int(no_id),
                        "entries": int(entries),
                        "individual_time_percent": float(ind_t),
                        "individual_alloc_percent": float(ind_a),
                        "inherited_time_percent": float(inh_t),
                        "inherited_alloc_percent": float(inh_a),
                    }
                )

    if (
        not metadata["title"]
        or not saw_time
        or not saw_alloc
        or not (top_summary or tree_nodes)
    ):
        raise ValueError("Unsupported, incomplete, or empty GHC profile")

    # Identify Anomalies / Space Leaks
    anomalies: list[str] = []
    for item in top_summary:
        # High allocation (> 40%) but low computation time (< 10%) often signals thunk allocation churn / space leak
        if item["alloc_percent"] >= 40.0 and item["time_percent"] <= 10.0:
            anomalies.append(
                f"POTENTIAL SPACE LEAK / CHURN: '{item['cost_centre']}' ({item['module']}) accounts for {item['alloc_percent']}% of allocations but only {item['time_percent']}% of time. Check for unforced thunk accumulation (e.g. lazy fold)."
            )
        # Extreme CPU bottleneck
        if item["time_percent"] >= 60.0:
            anomalies.append(
                f"DOMINANT CPU BOTTLENECK: '{item['cost_centre']}' ({item['module']}) consumes {item['time_percent']}% of CPU time. Primary target for strictness/unboxing optimization."
            )

    return {
        "metadata": metadata,
        "top_summary": top_summary,
        "tree_nodes": tree_nodes,
        "anomalies": anomalies,
    }


def print_report(data: dict[str, Any]) -> None:
    """Print formatted summary tables and diagnosis to terminal."""
    meta = data["metadata"]
    print("=" * 72)
    print("GHC PROFILING REPORT ANALYSIS")
    print(
        f"Total CPU Time:   {meta['total_time_secs']:.3f} seconds ({meta['total_ticks']} ticks @ {meta['tick_interval_us']}us, {meta['cores']} cores)"
    )
    print(
        f"Total Allocation: {meta['total_alloc_bytes']:,} bytes ({meta['total_alloc_bytes'] / (1024 * 1024):.2f} MiB)"
    )
    print("=" * 72)

    top_summary = data["top_summary"]
    if top_summary:
        print("\n=== TOP COST CENTRES BY RESOURCE USAGE ===")
        print(
            f"{'COST CENTRE':<22} | {'MODULE':<12} | {'% TIME':<8} | {'% ALLOC':<8} | {'SOURCE'}"
        )
        print("-" * 72)
        for item in top_summary[:15]:
            print(
                f"{item['cost_centre']:<22} | {item['module']:<12} | {item['time_percent']:>6.1f}% | {item['alloc_percent']:>6.1f}% | {item['src']}"
            )
        print("-" * 72)

    anomalies = data["anomalies"]
    if anomalies:
        print("\n=== DIAGNOSTIC ALERTS & INSIGHTS ===")
        for alert in anomalies:
            print(f"[*] {alert}")
    else:
        print(
            "\n[+] No heuristic alerts; this does not establish balanced resource use."
        )
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GHC .prof cost-centre and allocation profile analyzer."
    )
    parser.add_argument(
        "prof_file",
        help="Path to GHC profiling output file (e.g. Main.prof)",
    )
    parser.add_argument(
        "--json-out",
        "-j",
        type=str,
        default=None,
        help="Path to export parsed report in JSON format",
    )

    args = parser.parse_args()

    try:
        with open(args.prof_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        print(f"Error opening '{args.prof_file}': {e}", file=sys.stderr)
        return 1

    try:
        parsed = parse_ghc_prof(content)
    except ValueError as exc:
        print(f"Invalid profile: {exc}", file=sys.stderr)
        return 2
    print_report(parsed)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)
        print(f"\n[+] Saved JSON analysis to: {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
