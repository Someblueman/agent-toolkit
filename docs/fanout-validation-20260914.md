# Fanout harness qualification — 2026-09-14

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
`openai-codex/gpt-5.6-sol` in this original test. That revision left Pi model selection
to its native settings; the subsequent change below sets a fanout default.

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

## Pi DeepSeek default and Claude Code support

Pi fanout workers now default to `opencode-go/deepseek-v4.1-flash`; `--model` still
passes native overrides through. Standalone Pi settings are not modified.
Claude Code is selectable with `--harness claude`. It uses native print-mode structured
output, private stdin prompt files, no session persistence, and the shared bounded
process runner. Only successful result envelopes with valid structured receipts count.
Claude model selection remains native unless the caller supplies `--model`.

Installed Claude Code version: 2.1.270; Pi: 0.85.1. Two concurrent workers per harness
reviewed the faulty `total` function with a 180-second deadline, returning 2/2 valid
reports each. All four input/actual/expected examples were independently checked against
Python arithmetic. Pi assistant events confirmed `opencode-go/deepseek-v4.1-flash`.
Claude's native model usage reported `claude-fable-5-1` plus a small Haiku auxiliary call.
The source stayed unchanged, but native Python verification created `__pycache__` in
that temporary workspace: these harnesses retain normal tools, not a read-only sandbox.

A second test placed a fresh random marker and three integers in `sample.txt`, omitted
those values from the prompt, and required file reading without shell commands. Each
harness ran two concurrent workers with a 150-second deadline. Both returned 2/2 exact
marker matches, the correct integer list, and the independently verified sum of 81.
That workspace still contained only its unchanged input file. Across both tasks,
4/4 Pi and 4/4 Claude Code reports were validated.

New subprocess tests cover private stdin delivery, native Claude model selection and
explicit overrides, partial quorum, malformed output, nonzero exits, capture-size
rejection, and timeout with one attempt. Parser cases reject nonterminal envelopes,
error subtypes, text-only receipts, wrong worker ids, and invalid payloads. Pi's default
and explicit thinking-suffix override are checked separately.

Verification passed: all 73 fanout tests, the full repository quality check, direct
Ruff lint/format checks on changed Python files, and `git diff --check`. The Codex skill
was refreshed through the installer and its read-only `--check` comparison passed.

Claude Code print mode skips its workspace trust dialog; callers must use trusted
working directories. Configured permissions, tools, hooks, plugins, and project context
are retained. Session persistence is disabled, but hooks/plugins may write other state.
See the [native headless contract](https://code.claude.com/docs/en/headless).

Local retained artifacts: `/var/folders/sp/gftbmpy17y1_q_6cp75p8gm40000gn/T/fanout-claude-pi-gb2ijho8`.
