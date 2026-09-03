The event tool records one event per invocation:

    python3 cli.py record <tag> <message>

Implement the `record` action. It emits exactly one line to stdout:

    YYYY-MM-DDTHH:MM:SS <tag> <message>

- The timestamp is the current UTC time, zero-padded, formatted
  `YYYY-MM-DDTHH:MM:SS`.
- `<tag>` is the second CLI argument and `<message>` the third; the
  message may contain spaces.
- "Exactly one line" means the formatted text followed by a single
  trailing newline.
- The process exits 0 on success. Unknown actions and wrong argument
  counts exit non-zero with a message on stderr.

`record(tag, message, out)` lives in `recorder.py`: it writes the line
to the given output stream and returns nothing. Argument parsing for
the three CLI options already exists in `config.py`. `cli.py` is the
entry point and the only caller of `record`.

`tests/test_record.py` has a behavior test for the emitted line shape.

Constraints:
- Edit only `recorder.py` and `cli.py` (plus `tests/` if you add tests).
- Python stdlib only; no external dependencies.
