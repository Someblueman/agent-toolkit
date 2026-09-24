# Claude bridge

`claude-bridge` lets a local Codex task exchange messages with Claude Code without manual
copy and paste. `start` returns immediately and starts one detached Claude process for
the exchange. `reply` sends another message to that live process, which keeps its context
in memory. Codex can continue its work and collect each answer later. Use `close` when
the exchange is finished; this stops Claude and prevents further replies.

The default invocation uses `--restricted --safe-mode --tools "" --model opus --effort high`
with streaming JSON input and output and no Claude session persistence. Claude receives a
fixed peer-review system prompt plus the messages in this exchange. It has no workspace
tools or MCP tools. The bridge stores its own explicit transcript. If the worker exits,
the next reply starts a new process and replays successful turns once to restore context.
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
tools/claude-bridge/bin/claude-bridge close EXCHANGE_ID
```

`--message "short text"` is also accepted. `--message-file -` reads stdin. For tests or
custom launches, `start` accepts `--claude PATH`, `--timeout-seconds` (default 0,
no turn limit), and `--max-output-bytes` (default 1,000,000 for the final result).
Pass the global `--state-dir PATH` before the
command to override the state directory. Create message files with mode `0600` and remove
them after submission; the bridge keeps its own private copy.

`reply --timeout-seconds N` updates an existing exchange's turn limit for that reply and
later replies. Use 0 to remove the limit. The default for older exchanges stays as
recorded until changed. A
timed-out turn keeps its status; the bridge does not retry it.
The timeout applies to each active Claude turn; it does not expire an idle exchange.
`cancel` stops the active turn and its Claude process, while leaving the exchange open
for a later reply. `close` stops Claude even when idle and marks the exchange closed.

All commands print JSON with `exchange_id`, `turn`, and `state`. Completed results also
include `response`, observed model IDs, and cost when Claude reports them. `start`,
`reply`, `status`, `cancel`, and `close` exit 0 after a valid operation. `wait` and `result` exit 0
for success, 3 while pending, and 1 for a failed, timed out, or cancelled turn. Invalid
arguments or state exit 2. `wait` polls for at most its requested duration. No automatic
retry occurs after an uncertain outcome.

State defaults to `${XDG_STATE_HOME:-~/.local/state}/agent-toolkit/claude-bridge/`.
Directories use mode `0700`; request, response, status, and raw output files use `0600`.
Each exchange contains its configured model, effort, workspace path, and numbered turns.
The restart prompt includes only earlier successful turns. While Claude remains running,
each follow-up sends only the new message. The bridge does not truncate the exchange or
impose a character cap. The selected Claude model's context
window is measured in tokens, including room for its reply and thinking. If Claude
rejects a long prompt, start a new exchange with a summary.

## Verification

```sh
python3 -m unittest discover -s tools/claude-bridge/tests -v
tools/quality/bin/quality check
```
