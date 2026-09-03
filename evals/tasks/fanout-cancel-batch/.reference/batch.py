"""Batch runner for async jobs -- reference solution.

Structured concurrency via asyncio.TaskGroup: all jobs run concurrently, the
first DataError aborts the group (siblings are cancelled deterministically),
all DataErrors are collected with except*, and a single BatchFailed carries
every failed index. Results are gathered by task identity, so ordering matches
input order regardless of completion order. TaskGroup guarantees no task
outlives the block.
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
    tasks = []
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(job.execute()) for job in jobs]
    except* DataError as eg:
        failed = sorted(
            i for i, t in enumerate(tasks)
            if t.done() and not t.cancelled() and isinstance(t.exception(), DataError)
        )
        raise BatchFailed(
            f"batch failed at indexes {failed}", failed_indexes=failed
        ) from eg
    return [t.result() for t in tasks]
