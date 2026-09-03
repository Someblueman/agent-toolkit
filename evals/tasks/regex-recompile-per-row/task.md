Our audit-log normalizer is too slow. Every batch we ingest is piped through
(`python3 main.py < batch.log`), and on a typical batch of ~35,000 rows it
takes seconds of wall time. Make the pipeline substantially faster — our
target is at least 3x — while writing exactly the same bytes to stdout.

The contract (see `main.py`): the pipeline reads audit rows on stdin, one per
line, extracts the structured fields of each row, and writes one normalized
row per successfully parsed input row on stdout. Rows that fail to parse
produce no output row. stdout must stay byte-identical for any input.

You can generate batches for measurement with `python3 gen_batch.py [rows]
[seed]` (e.g. `python3 gen_batch.py 40000 1 > batch.log`).

Constraints:
- Edit only `main.py`.
- Keep the module-level functions `extract_fields` and `rolling_hash` in
  `main.py`: you may rewrite their bodies and restructure everything around
  them, but both must remain defined and still be called for each input row,
  as today.
- `main.py` reads only from stdin and writes only to stdout: no file I/O, no
  environment-dependent behavior, no subprocesses.
- stdlib only; python3.
