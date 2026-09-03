"""Slow line deduplicator. See the task for what to optimize."""
from pathlib import Path


def first_unique_lines(lines: list[str]) -> list[str]:
    """Return lines in first-seen order, dropping later duplicates."""
    out: list[str] = []
    for line in lines:
        if line not in out:
            out.append(line)
    return out


def main() -> None:
    data = Path("data.txt").read_text().splitlines()
    result = first_unique_lines(data)
    print(f"unique lines: {len(result)}")
