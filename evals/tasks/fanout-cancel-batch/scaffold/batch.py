"""Batch runner for async jobs.

The ingestion pipeline hands `run_batch` a list of jobs. Every job -- whether
one of our `Job` instances below or a third-party object -- exposes the same
interface: `async def execute() -> int`.

Today `run_batch` runs the jobs one after another and lets a raw `DataError`
escape. That is wrong on both counts: the jobs are independent, so they should
all make progress at the same time, and a batch in which one job hit a data
problem must surface as a `BatchFailed`, not a bare `DataError`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

STEP = 0.02  # seconds per await slice; jobs sleep cooperatively so they stay cancellable


class DataError(Exception):
    """A job's payload is malformed; retrying will not help."""


class BatchFailed(Exception):
    """Raised instead of DataError when one or more jobs in a batch fail."""

    def __init__(self, message: str, failed_indexes: list[int]):
        super().__init__(message)
        self.failed_indexes = failed_indexes


@dataclass
class Job:
    name: str
    result: int = 0
    duration: float = 0.0  # seconds of async work
    fails: bool = False

    async def execute(self) -> int:
        if self.fails:
            raise DataError(f"job {self.name!r}: malformed payload")
        steps = max(1, round(self.duration / STEP))
        for _ in range(steps):
            await asyncio.sleep(STEP)
        return self.result


async def run_batch(jobs: list[Job]) -> list[int]:
    results = []
    for job in jobs:
        results.append(await job.execute())
    return results
