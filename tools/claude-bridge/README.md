# Claude bridge

`claude-bridge` lets a local Codex task exchange messages with Claude Code without manual
copy and paste. `start` and `reply` return immediately; a detached worker runs Claude and
writes a private result. Codex can continue its work and collect the answer later.

The default invocation uses `--restricted --safe-mode --tools "" --model opus --effort high`
with JSON output and no Claude session persistence. Claude receives a fixed peer-review
system prompt plus the messages in this exchange. It has no workspace tools or MCP tools.
The bridge stores its own explicit transcript and replays successful turns for follow-ups.
Claude Code must be installed and authenticated. Managed settings may still apply to
Claude Code; user and project settings, CLAUDE.md, hooks, plugins, and auto memory are
excluded by the selected modes. The tool is local and does not notify an idle Codex task.

## Commands

```sh
tools/claude-bridge/bin/claude-bridge start \
  --message-file /path/to/private-question.txt \
  [--working-directory /path/to/project] [--model opus] [--effort high]

tools/claude-bridge/bin/claude-bridge status EXCHANGE_ID
tools/claude-bridge/bin/claude-bridge wait EXCHANGE_ID --timeout-seconds 30
tools/claude-bridge/bin/claude-bridge result EXCHANGE_ID
tools/claude-bridge/bin/claude-bridge reply EXCHANGE_ID --message-file /path/to/private-followup.txt
tools/claude-bridge/bin/claude-bridge cancel EXCHANGE_ID
```

`--message "short text"` is also accepted. `--message-file -` reads stdin. For tests or
custom launches, `start` accepts `--claude PATH`, `--timeout-seconds` (default 1800), and
`--max-output-bytes` (default 1,000,000). Pass the global `--state-dir PATH` before the
command to override the state directory. Create message files with mode `0600` and remove
them after submission; the bridge keeps its own private copy.

`reply --timeout-seconds N` updates an existing exchange's turn limit for that reply and
later replies. The default for older exchanges stays as recorded until changed. A
timed-out turn keeps its status and partial output, if any; the bridge does not retry it.

All commands print JSON with `exchange_id`, `turn`, and `state`. Completed results also
include `response`, observed model IDs, and cost when Claude reports them. `start`,
`reply`, `status`, and `cancel` exit 0 after a valid operation. `wait` and `result` exit 0
for success, 3 while pending, and 1 for a failed, timed out, or cancelled turn. Invalid
arguments or state exit 2. `wait` polls for at most its requested duration. No automatic
retry occurs after an uncertain outcome.

State defaults to `${XDG_STATE_HOME:-~/.local/state}/agent-toolkit/claude-bridge/`.
Directories use mode `0700`; request, response, status, and raw output files use `0600`.
Each exchange contains its configured model, effort, workspace path, and numbered turns.
The prompt for a new turn includes only earlier successful turns. The bridge does not
truncate the exchange or impose a character cap. The selected Claude model's context
window is measured in tokens, including room for its reply and thinking. If Claude
rejects a long prompt, start a new exchange with a summary.

## Verification

```sh
python3 -m unittest discover -s tools/claude-bridge/tests -v
tools/quality/bin/quality check
```
