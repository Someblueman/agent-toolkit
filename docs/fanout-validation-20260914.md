# Fanout OpenCode recovery and Pi qualification — 2026-09-14

## Reported failure and fixes

The retained Hydra review artifacts showed a shared database lock at startup, provider
HTTP 400 rejecting forced structured-output tool choice, synchronous prompt failures near
305 seconds, and a reported OS error without a usable packet. The exact historical OS
operation cannot be identified from the retained artifacts; its error class is reproduced
at the worker port-allocation boundary in the regression suite.

- Each OpenCode worker now uses its own `OPENCODE_DB` under the private result directory.
- One `promptAsync` submission plus short status/message requests replaces the long POST.
  Polling does not resubmit tasks. Model thinking settings remain intact.
- Final JSON is validated locally. Forced tool-choice schemas and the DeepSeek thinking
  override are removed. SDK API errors are retained in the error envelope.
- OS/value/type failures become worker `runner_error` receipts; sibling results survive.
- `OPENCODE_GOAL_STATE_PATH` routes the installed goal plugin's state outside the workspace.
  Plugin settings, auth, project configuration, and permissions are not disabled.
- Pi uses its native ephemeral JSON CLI and validates the final completed assistant message.

## Live acceptance

Installed versions: OpenCode 1.18.30; Pi 0.85.1. OpenCode model:
`opencode-go/deepseek-v4.1-flash`. Pi's native default resolved to
`openai-codex/gpt-5.6-sol` in this test; fanout does not force that default.

Both harnesses reviewed a known faulty `total(values)` returning `sum(values[:-1])`.
Every final report's input, expected total, and observed total was independently checked
with ordinary Python arithmetic. Each harness ran four simultaneous workers, with a
120-second per-worker deadline and all four results required.

| Run | Valid results | Elapsed |
|---|---|---|
| opencode-repeat | 4/4 | 8.747 s |
| pi-repeat | 4/4 | 10.607 s |

The clean workspace contained only `AGENTS.md` and `calc.py` before and after the run;
source contents were unchanged. OpenCode databases and goal state stayed in output
folders. An earlier four-worker OpenCode run also completed 4/4. Pi's initial run was 1/2:
one model returned an object in `result_json`; it was rejected, and an explicit JSON
example improved the repeat without relaxing validation or adding automatic retries.

Regression coverage includes per-worker database locks, OS permission/exec failures,
async SDK completion and API errors, Pi model forwarding, terminal/partial/error events,
quorum, timeout, and existing Muse/Agy lifecycle behavior. Run:

```sh
python3 -m unittest discover -s tools/fanout/tests -p 'test_*.py' -v
tools/quality/bin/quality check
```

This establishes bounded local acceptance, not guaranteed provider availability or OS
read-only enforcement for arbitrary plugins/tools. An explicit goal-plugin state-path
option can override the environment route. Existing sandbox restrictions are preserved;
permission-denied operations are reported rather than bypassed.

Local retained live artifacts: `/var/folders/sp/gftbmpy17y1_q_6cp75p8gm40000gn/T/fanout-repair-dz79cgeg`.
