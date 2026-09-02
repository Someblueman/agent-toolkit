"""
Baseline Implementation: Multi-Pass Intermediate Allocating Data Pipeline

Demonstrates an anti-pattern common in naive functional or data-processing code:
every transformation step materializes and allocates intermediate collections in memory.
"""

from __future__ import annotations

from typing import Any, Dict, List


def process_log_records_multi_pass(raw_text: str, target_status: int, min_duration_ms: float) -> Dict[str, Any]:
    """
    Processes raw log text through 6 separate materializing stages.
    """
    # Stage 1: Materialize split lines (Allocation 1)
    raw_lines: List[str] = raw_text.splitlines()

    # Stage 2: Filter and strip lines (Allocation 2)
    stripped_lines: List[str] = []
    for line in raw_lines:
        s = line.strip()
        if s:
            stripped_lines.append(s)

    # Stage 3: Filter comments (Allocation 3)
    data_lines: List[str] = []
    for line in stripped_lines:
        if not line.startswith("#"):
            data_lines.append(line)

    # Stage 4: Tokenize fields (Allocation 4)
    tokenized: List[List[str]] = []
    for line in data_lines:
        fields = [f.strip() for f in line.split(",")]
        if len(fields) >= 4:
            tokenized.append(fields)

    # Stage 5: Parse types into dictionaries (Allocation 5)
    records: List[Dict[str, Any]] = []
    for fields in tokenized:
        try:
            records.append({
                "timestamp": int(fields[0]),
                "endpoint": fields[1],
                "status": int(fields[2]),
                "duration_ms": float(fields[3]),
            })
        except (ValueError, IndexError):
            continue

    # Stage 6: Filter by criteria (Allocation 6)
    matching_records: List[Dict[str, Any]] = []
    for r in records:
        if r["status"] == target_status and r["duration_ms"] >= min_duration_ms:
            matching_records.append(r)

    # Stage 7: Aggregate
    total_duration = sum(r["duration_ms"] for r in matching_records)
    count = len(matching_records)
    avg_duration = (total_duration / count) if count > 0 else 0.0

    return {
        "matched_count": count,
        "total_duration_ms": round(total_duration, 3),
        "avg_duration_ms": round(avg_duration, 3),
    }
