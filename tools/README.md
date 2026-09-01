# tools/

Standalone tools that hooks and scripts can invoke. Tools are *capabilities* — things the toolkit can do — and are not tied to any single agent's tool API.

## Convention

A tool lives at `tools/<tool-name>/`:

- A `bin/<tool-name>` executable (the CLI entry point).
- A `README.md` documenting its interface (input, output, exit codes).
- Optional `lib/` for shared code.

Tools are designed to be callable from:

- A shell: `tools/repo-inspector/bin/repo-inspector <args>`
- An agent hook: hooks wrap the call and translate events.
- Another tool: tools may compose each other.

## Existing tools

- [repo-inspector/](repo-inspector/) — placeholder.
- [context-builder/](context-builder/) — placeholder.