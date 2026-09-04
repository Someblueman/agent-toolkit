# AFK plan format

The active plan is a YAML file named `plan.yaml` beneath
`${AFK_HOME:-~/.afk}/plans/<unique-plan-name>/`. Instruction paths are relative
to the directory containing that file.

```yaml
version: 1
name: project-change-20260901T120000Z
base: main
max_attempts: 3

protected_paths:
  - .github/

tasks:
  - id: implement-server
    instructions: tasks/implement-server.md
    depends_on: []
    checks:
      - [uv, run, pytest, -q, tests/test_server.py]

  - id: integrate-cli
    instructions: tasks/integrate-cli.md
    depends_on: [implement-server]
    checks:
      - [uv, run, pytest, -q, tests/test_cli.py]

final_checks:
  - [uv, run, pytest, -q]
  - [uv, run, ruff, check, .]
```

Required rules enforced by `afk plan lint`:

- `version` is exactly `1`.
- `name` and `base` are non-empty. `name` contains only letters, numbers,
  periods, underscores, and dashes, and begins with a letter or number.
- `max_attempts` is an integer from `1` through `4`; omission means `3`. Use
  three unless the task is unusually cheap or expensive: later attempts receive
  authoritative controller validation from the previous candidate.
- `protected_paths` is optional. Every entry is a repository-relative path with
  no `..` traversal. Protect only paths the approved work must not touch.
- `tasks` is a non-empty list. IDs are unique and use the same character rules
  as `name`.
- Every task has an existing repository-external Markdown instruction file, a
  `depends_on` list containing existing task IDs, and a non-empty `checks` list.
- Dependencies are unique, non-self-referential, and acyclic.
- `checks` and `final_checks` are non-empty lists of non-empty argument arrays.
  Each argument is a string. Do not use shell command strings, pipes, redirects,
  substitutions, or environment assignments; invoke the executable directly.
- `final_checks` is required and validates the integrated change.

Task instruction files should state the outcome, behavioral constraints,
directly relevant files or modules, focused test expectations, and meaningful
out-of-scope boundaries. Do not repeat generic coding advice or prescribe an
abstraction unless the repository already requires it.

Plan storage example:

```text
~/.afk/plans/project-change-20260901T120000Z/
|-- plan.yaml
`-- tasks/
    |-- implement-server.md
    `-- integrate-cli.md
```
