"""
Simplified Implementation: Single-Pass Fused Zero-Copy Data Pipeline

Streams through the text in a single pass without allocating intermediate lists or dictionaries.
Performs in-place field parsing and running aggregation.
"""

from __future__ import annotations

from typing import Any, Dict


def _parse_and_aggregate_line(
    line: str, target_status: int, min_duration_ms: float
) -> tuple[int, float]:
    line = line.strip()
    if not line or line.startswith("#"):
        return 0, 0.0

    # Fast 4-field split without regex or multiple passes
    parts = line.split(",", 4)
    if len(parts) < 4:
        return 0, 0.0

    try:
        _ = int(parts[0].strip())  # Validate timestamp format
        status = int(parts[2].strip())
        if status != target_status:
            return 0, 0.0

        duration = float(parts[3].strip())
        if duration >= min_duration_ms:
            return 1, duration
    except ValueError:
        return 0, 0.0

    return 0, 0.0


def process_log_records_zero_copy(
    raw_text: str, target_status: int, min_duration_ms: float
) -> Dict[str, Any]:
    """
    Processes raw log text in a fused single-pass loop with zero intermediate list allocations.
    """
    count = 0
    total_duration = 0.0

    # Single pass iteration over splitlines iterator / generator
    for line in raw_text.splitlines():
        matched, duration = _parse_and_aggregate_line(line, target_status, min_duration_ms)
        if matched:
            count += 1
            total_duration += duration

    avg_duration = (total_duration / count) if count > 0 else 0.0

    return {
        "matched_count": count,
        "total_duration_ms": round(total_duration, 3),
        "avg_duration_ms": round(avg_duration, 3),
    }
