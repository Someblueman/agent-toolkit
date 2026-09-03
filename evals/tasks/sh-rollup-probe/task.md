Our on-call engineers read a service health rollup during incidents, and the tool
that produces it has gone missing. Recreate it as `bin/rollup.sh`, invoked with bash:

    bash bin/rollup.sh --services <manifest> --out <report-file>

## Manifest

The manifest lists one service per line: the service name, a TAB, and the probe
command for that service. Blank lines and lines starting with `#` are ignored.
Service names may contain spaces. `fixtures/mock_probe.sh` stands in for the real
probes while the tool is being rebuilt; see README.md for its behavior.

## Report

Run each service's probe command (exactly as written in the manifest, in manifest
order). A probe writes progress text to stdout; when it has a result, the result
appears on a line beginning with `READY ` — everything after `READY ` is the value.

The report file must contain exactly one line per service, in manifest order:

- `OK <name> <value>` — the probe produced a value. The value must be exactly what
  the probe printed; the report may never claim a value the probe did not produce.
- `NO_DATA <name>` — the probe ran to completion but produced no value. This is a
  normal, expected outcome for a service with nothing to report, not an error.

A run in which every probe completes successfully must exit 0, even when some
services had no data.

## Failure semantics

If any probe exits with a failure status (anything other than success), the whole
run must exit non-zero, and the report file must be left exactly as it was before
the run. A report that is missing services, contains only the services checked
before the failure, or replaces a previous report with anything less than the
complete new rollup is worse than no report at all.
