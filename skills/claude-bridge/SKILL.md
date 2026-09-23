---
name: claude-bridge
description: Exchange isolated, asynchronous messages with Claude when the user asks Codex and Claude to collaborate.
---

# Claude bridge

Use the local `tools/claude-bridge/bin/claude-bridge` CLI for a continuing exchange with
Claude. Codex remains responsible for the work, checks material claims against the actual
evidence, and decides what to adopt. Claude receives only the messages Codex sends and the
earlier successful turns in this exchange. It cannot read the workspace or use tools.

Locate the toolkit checkout from this skill's source path. For an installed Codex copy,
read `agent-toolkit-root.txt` two directories above the skill directory as plain text;
never source or execute it. Check that the CLI exists and is executable. Claude Code must
be installed and authenticated. This bridge works in local Codex tasks.

Prepare a concise message containing the question, relevant evidence, and links or file
excerpts Claude needs. Use `--message-file` for substantial text so shell quoting cannot
change it. Create that temporary file with mode `0600` and remove it after submission;
the bridge keeps a private copy. Call `start`; retain the returned `exchange_id`. Continue
useful local work,
then call `status` or `wait`. `result` returns Claude's answer when ready. Use `reply` with
the same ID for follow-up questions. One reply may run at a time per exchange.

```sh
"$TOOLKIT_ROOT/tools/claude-bridge/bin/claude-bridge" start --message-file /path/to/message.txt
"$TOOLKIT_ROOT/tools/claude-bridge/bin/claude-bridge" wait EXCHANGE_ID --timeout-seconds 30
"$TOOLKIT_ROOT/tools/claude-bridge/bin/claude-bridge" reply EXCHANGE_ID \
  --message-file /path/to/followup.txt
```

The CLI returns JSON. `wait` and `result` exit 0 on success, 3 while pending, and 1 on a
failed, timed out, or cancelled turn. Inspect the private exchange record before retrying
a request after an uncertain outcome; the bridge never retries automatically. Stop an
unneeded run with `cancel EXCHANGE_ID`. The tool preserves state across Codex turns but
does not wake a completed Codex turn on its own.

The default model is `opus` at `high` effort. The bridge invokes Claude with restricted
and safe modes, no tools, and no Claude session persistence. Its local transcript is the
only exchange history it intentionally supplies. Read
`$TOOLKIT_ROOT/tools/claude-bridge/README.md` for configuration, state location, and exact
command behavior.
