#!/usr/bin/env bash
# UserPromptSubmit hook: on the first prompt of each session, ask Claude to run the
# ambition-check skill. Later prompts in the same session pass through untouched.
# Input: the hook's JSON on stdin (uses .session_id and .prompt).
# Output: hookSpecificOutput.additionalContext JSON on the first prompt, nothing otherwise.
set -euo pipefail

if [ "${1:-}" = --help ]; then
  cat <<'USAGE'
Usage: ambition-check.sh < hook-input.json
Claude Code UserPromptSubmit hook. On the first ordinary prompt of a session it prints
JSON asking Claude to apply the ambition-check skill. With CLAUDE_WORKER set it tells
the session to do its task without delegating. Register it under hooks.UserPromptSubmit.
USAGE
  exit 0
fi

state_dir="${HOME}/.claude/state/ambition-check"
input="$(cat)"

# A session launched by another agent as a worker (for example a fanout worker)
# sets CLAUDE_WORKER=1: it should do its task, not orchestrate or question the ask.
if [ -n "${CLAUDE_WORKER:-}" ]; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: "This session is a worker launched by another agent (CLAUDE_WORKER is set). Do the task yourself. Ignore the Orchestrator output style'\''s delegation guidance, skip the ambition check, and do not start subagents or Sol runs unless the task explicitly asks for them."
    }
  }'
  exit 0
fi

session_id="$(jq -r '.session_id // empty' <<<"$input")"
prompt="$(jq -r '.prompt // empty' <<<"$input")"

[ -n "$session_id" ] || exit 0
case "$session_id" in */* | .*) exit 0 ;; esac

# Slash commands carry their own instructions; let them run as written, and keep
# the check for the first ordinary prompt.
case "$prompt" in /*) exit 0 ;; esac

mkdir -p "$state_dir"
marker="$state_dir/$session_id"
[ -e "$marker" ] && exit 0
: >"$marker"

# Forget sessions older than two weeks.
find "$state_dir" -type f -mtime +14 -delete 2>/dev/null || true

jq -n '{
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: "This is the first prompt of the session. Before starting work, apply the ambition-check skill: decide whether the request is broad or open-ended enough to need it; if so, climb one rung to the outcome it serves and agree measurable success criteria (asking at most one AskUserQuestion round, or stating your assumptions and proceeding). If the request is a question, a small concrete task or already specific, skip the check silently."
  }
}'
