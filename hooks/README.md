# hooks/

Hooks are small executable scripts invoked by agents at lifecycle points. They are agent-agnostic: the file in this directory is the canonical implementation, and `configs/<agent>/` provides the wiring for each agent.

## Categories

- `pre-tool/` — run before an agent calls a tool.
- `post-tool/` — run after an agent calls a tool.
- `session/` — run at session start, end, or on compaction.

## Convention

- Files are executable shell scripts. Bash is preferred; Python with a shebang is fine.
- The script receives a JSON payload on stdin describing the event.
- Exit code 0 = pass; non-zero = block (for pre-tool hooks) or warn (for post-tool hooks).
- Keep them stateless. Anything stateful goes in `tools/`.

## Adding a hook

1. Drop the script in the appropriate category directory.
2. Document it inline with a header comment.
3. Add the agent-specific wiring in `configs/<agent>/`.