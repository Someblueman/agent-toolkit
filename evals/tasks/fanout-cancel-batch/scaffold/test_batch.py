"""Visible tests for the documented batch contract.

Run with: python3 -m unittest test_batch -v

These cover the basic behavior only. The full acceptance suite additionally
checks how long the batch takes and what it leaves behind on the event loop.
"""
import asyncio
import unittest

from batch import BatchFailed, DataError, Job, run_batch


class TestBatch(unittest.IsolatedAsyncioTestCase):
    async def test_all_success_returns_results_in_input_order(self):
        jobs = [
            Job("a", result=10, duration=0.06),
            Job("b", result=11, duration=0.02),
            Job("c", result=12, duration=0.04),
            Job("d", result=13, duration=0.02),
        ]
        self.assertEqual(await run_batch(jobs), [10, 11, 12, 13])

    async def test_data_error_raises_batch_failed_with_failed_index(self):
        jobs = [
            Job("a", result=1, duration=0.05),
            Job("b", result=2, duration=0.05),
            Job("bad", fails=True),
            Job("d", result=4, duration=0.05),
        ]
        with self.assertRaises(BatchFailed) as cm:
            await run_batch(jobs)
        self.assertEqual(cm.exception.failed_indexes, [2])

    async def test_data_error_is_not_raised_raw(self):
        with self.assertRaises(BatchFailed):
            await run_batch([Job("solo", fails=True)])


if __name__ == "__main__":
    unittest.main()
