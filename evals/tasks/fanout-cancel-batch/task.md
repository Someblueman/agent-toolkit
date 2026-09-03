The ingestion pipeline in `batch.py` is misbehaving. `run_batch(jobs)` receives
a list of jobs; every job -- our `Job` class or a third-party object -- exposes
the same interface: `async def execute() -> int`.

Current symptoms:

- Jobs are worked on one after another. With independent jobs, the batch takes
  roughly the *sum* of all job durations instead of about the duration of the
  single slowest job.
- When one job hits a data problem, the batch keeps grinding through the
  remaining jobs to the bitter end. A batch where one job fails immediately
  still occupies the pipeline for the full runtime of the other jobs.
- The failure surfaces as a raw `DataError` instead of the `BatchFailed` the
  pipeline's caller expects.

Required behavior of `run_batch(jobs)`:

- All jobs run concurrently, not sequentially: a batch of N similar-duration
  jobs takes about as long as one of them, not N times as long.
- If any job raises `DataError`, the batch must stop waiting on the
  still-running jobs promptly -- it must not stay alive anywhere near the full
  duration of the remaining jobs -- and raise `BatchFailed` whose
  `failed_indexes` attribute lists the index of *every* job that raised
  `DataError`, in ascending order.
- If every job succeeds, return the job results as a list in the same order as
  the input jobs (results must line up with their own job, not with completion
  order).
- When `run_batch` returns or raises, nothing it started may still be running
  in the background: the caller's event loop must be left with no pending
  leftovers from the batch, and no "task destroyed while pending" warnings.

Constraints:

- Edit only `batch.py`. Stdlib only. Python 3.11+.
- Keep `Job`, `DataError`, and `BatchFailed` as they are (names, signatures,
  attributes); third-party job objects only need `execute()`.
- The pipeline measures batch wall time; a correct implementation completes
  both a 6-job batch of ~0.1s jobs well under a second and a batch containing
  one immediate failure plus one 4s job in well under 1.5s.
