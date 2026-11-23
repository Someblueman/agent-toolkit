# Global instructions

## Subagents

Start every subagent on Claude Sonnet 5.5 (`claude-sonnet-5-5`): pass `model: "sonnet"` on each
Agent tool call (the alias resolves to the newest Sonnet available), unless the task explicitly
calls for another model.

## Delegation

The main session acts as an orchestrator: when to delegate, and to whom (Sonnet subagents or
ChatGPT Sol 6.2 through the `sol` skill), is set out in the Orchestrator output style. There is
plenty of Sol quota.

If you are a subagent or a fork, do the work you were given yourself. Don't delegate further, and
don't start Sol runs unless your brief asks for one.
