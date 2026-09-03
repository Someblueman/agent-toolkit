# Service rollup harness

`bin/rollup.sh` produces a health rollup report for a set of services. The
service list, the probe command for each service, and the report format are
described in the task description; this README documents the fixtures.

## Manifest

The manifest is UTF-8 text, one service per line:

    <service name> TAB <probe command>

Blank lines and lines starting with `#` are ignored. Service names may contain
spaces (they cannot contain tabs — the tab is the field separator). An example
manifest is provided at `services/manifest.example`.

## Probe contract (`fixtures/mock_probe.sh`)

The probe command is invoked with its arguments as given in the manifest. Every
probe:

- writes human-readable progress text to stdout;
- prints a line beginning with `READY ` when it has a result; the remainder of
  that line is the value;
- exits 0 when it ran to completion (with or without a result), and non-zero
  when it failed.

Available variants:

| Variant       | stdout                              | exit |
|---------------|-------------------------------------|------|
| `ok-marker`   | progress lines + `READY <value>`    | 0    |
| `ok-empty`    | progress lines only, no result      | 0    |
| `fail-exit-3` | progress lines, error on stderr     | 3    |

An unknown variant exits 2 with a message on stderr. The optional second
argument overrides the reported value of `ok-marker`.
