# Named workflows and configurable models

Use workflows for structured review or owned implementation. Plain `--harness` fanout
remains available and retains its version-3 packet. Workflow mode emits version 4.

| Workflow | Task | Starter roster |
| --- | --- | --- |
| `review-plan` | Review assumptions, feasibility, interfaces, and verification | Gemini 3.8 Flash High / Agy + Fable / Claude Code |
| `critique` | Give constructive feedback directly to the calling agent | Gemini 3.8 Flash High / Agy + Fable / Claude Code |
| `bug-hunt` | Find concrete behavioral defects; distinguish reproductions from hypotheses | DeepSeek / Pi + Gemini / Agy + Fable / Claude Code |
| `implement` | Deliver separately owned changes in supplied worktrees | DeepSeek / Pi and Sonnet / Claude Code implementer pool |

Models are roster data, not workflow requirements. Inspect `rosters/defaults.json` for
exact starter routes. Every configured review member runs once; every implementation
assignment runs once using its selected member. All dispatched workers must return valid,
completed results. One model may appear in several assignments. An unused implementer
pool member does not launch. There are no automatic task resubmissions in workflow mode.
Native provider retries remain within each worker's deadline. Agy stays read-only.

## Calling the workflow

Resolve `TOOLKIT_ROOT` using the main skill's installation instructions. Example:

```sh
"$TOOLKIT_ROOT/tools/fanout/bin/fanout" request.md --workflow review-plan \
  --working-directory /path/to/project --input /path/to/plan.md --describe
"$TOOLKIT_ROOT/tools/fanout/bin/fanout" request.md --workflow review-plan \
  --working-directory /path/to/project --input /path/to/plan.md --output /tmp/review-unique
```

Write the request file with the user's objective, constraints, exact target paths, and
relevant context. Workers do not inherit the caller's conversation. `--input` may repeat;
it records hashes of files outside the workspace as well as the request file. Name those
files in the request so workers know what to read. Normal project context/tools remain
available. For review and critique, prohibit edits and avoid commands that create files.

`--describe` reads configuration, inputs, Git metadata, and executable locations but does
not launch a harness or create outputs. It does not verify provider authentication or
quota. It is optional when execution is already authorized. Output must be outside all
worker checkouts; snapshots otherwise count fanout's own files as input mutations.
Workflow flags `--concurrency`, `--timeout-seconds`, and `--max-output-bytes` bound the run.
Workflows default to an 8 MB stdout/stderr acceptance threshold, accommodating native
incremental JSON streams; plain fanout retains 1 MB. Oversized output never counts.
Do not combine workflow mode with `--model`, `--harness`, `--workers`, `--agent`,
`--min-results`, or `--agy-retries`; configure members instead.

## Edit the model list

The user file is `$XDG_CONFIG_HOME/agent-toolkit/fanout.json`, or
`~/.config/agent-toolkit/fanout.json` when XDG_CONFIG_HOME is unset. An explicit
`--config /path/to/file.json` selects a different file instead. No project-local file is
automatically loaded. User configuration is not installer-owned.

```json
{
  "version": 1,
  "workflows": {
    "review-plan": {
      "members": [
        {"id": "gemini", "harness": "agy", "model": "gemini-3.8-flash-high"},
        {"id": "claude", "harness": "claude", "model": "claude-fable-5-1"},
        {"id": "extra", "harness": "pi", "model": "YOUR_PROVIDER/YOUR_MODEL", "focus": "Failure cases and recovery"}
      ]
    }
  }
}
```

A named workflow's list replaces its entire starter roster. Other workflows use their
starters. An empty or invalid roster fails; it never silently falls back to defaults.
Add a future GLM model by adding one member with its verified native provider/model route.
Model ids are passed through, with no fanout model allowlist. New harnesses need adapters;
new models in a supported harness need only roster entries and native authentication.
Do not invent provider names or provision credentials while editing a roster.

Member fields: required `id`, `harness`, `model`; optional `focus` and `settings`.
Ids must be unique letters/digits/underscores/hyphens, starting with a letter/digit.
Supported settings: OpenCode `{"agent":"build"}`; Agy `{"effort":"high"}`;
Claude Code `{"effort":"high"}`; Pi `{"effort":"high"}`. Effort choices are validated
per harness, then forwarded natively. Claude effort uses the subprocess environment;
Pi uses `--thinking`. Muse currently has no additional settings. Do not add arbitrary
CLI flags to configuration. These settings do not grant new permissions.

When asked to add/remove/change a model, edit only the selected user's roster. If there
is no user override yet, materialize that workflow's current effective members first so
adding one model preserves the others. Preserve unrelated workflows, write valid JSON,
and check `--describe`. Do not dispatch a run just to change configuration.

## Read results and use critique

Native workflow replies contain exactly `worker_id`, `outcome`, `summary`, and a direct
`payload` object matching the selected workflow schema. Blocked/failed replies use an
empty payload and explain the reason in summary. The normalized worker result retains
that payload. Plain mode's existing receipt shapes remain unchanged; workflow mode does
not accept JSON encoded inside a string or repair malformed model responses.

`packet.json` includes the resolved roster/configuration hashes, worker/member/assignment
identities, requested and observed model identities where native output supplies them,
native attempts, workflow validation, and any input-change or ownership failure.
`inputs.json` retains the source manifest and `resolved.json` the pre-run description.
Files are private. Unknown model/cost/token metadata stays unknown; `usage_complete`
indicates whether every attempt supplied both token and cost totals. Known totals can
be partial and are provider estimates, not spending limits.

Exit 0 means all assigned reports passed validation and required input checks. Exit 1
retains partial results/missing assignments or changed review inputs. Exit 2 means invalid
configuration, missing prerequisites/executables, or interruption. A schema-valid report
is still a worker claim. Verify evidence independently; do not present transport failure
as a clean review or treat multiple harnesses using one model as model diversity.

For `critique`, send the current draft/work plus a concise explanation of choices. Read
`strengths`, `improvements`, and `uncertainties` from every critic before revising. For each
material improvement, record accept/reject/defer with a short reason in a caller-authored
`disposition.json` or `disposition.md` alongside the packet. Verify claims, preserve sound
work, and apply accepted corrections only within existing authorization. Report meaningful
changes and unresolved disagreements to the user. Empty feedback lists are allowed.
Default to one round; no approval loop, automatic re-critique, or recursive fanout.

## Parallel implementation

Prepare authorized separate clean Git worktrees/checkouts at the same approved commit.
Fanout does not create, reset, delete, integrate, or publish worktrees. Assign shared files
to one owner or the caller. Split coupled work into sequential rounds if needed.

```json
{
  "version": 1,
  "assignments": [
    {
      "id": "parser",
      "member": "deepseek",
      "task": "Implement the parser per the supplied interface agreement.",
      "working_directory": "/absolute/owned-checkout",
      "base": "APPROVED_COMMIT",
      "owned_paths": ["src/parser.py", "tests/test_parser.py"],
      "acceptance": ["python3 -B -m unittest tests.test_parser"],
      "interfaces": "parse(text) returns the documented AST; preserve public exceptions.",
      "depends_on": []
    }
  ]
}
```

```sh
"$TOOLKIT_ROOT/tools/fanout/bin/fanout" request.md --workflow implement \
  --assignments assignments.json --output /tmp/implementation-unique
```

Each item names a roster member. `owned_paths` are literal relative files or directory
prefixes ending `/`, never globs, `..`, or `.git`. Include new files and tests. `acceptance`
contains the exact commands the worker must run and report; those reports still need
caller verification. `depends_on` lists prerequisite Git commits already ancestral to
`base`, not active assignment ids. Integrate dependencies into the approved base before
the next round. Agy and OpenCode's `plan` profile cannot implement.

Worktrees must be distinct, non-nested, at checkout roots, with non-overlapping ownership.
Submodules, symlinks, and special files are rejected for implementation. Before/after
manifests include ignored and untracked files; generated files outside ownership cause
nonconformance (use `python3 -B`, or put build output outside the checkout). Ownership is
final-state detection, not an OS write sandbox: transient edits later undone, `.git`
metadata, network operations, and external side effects are outside its guarantee.
Review snapshots similarly compare endpoints; they cannot prove no transient changes.

Retain failed/nonconforming worker changes for inspection. The calling agent reviews
`git diff BASE..HEAD` plus any uncommitted changes, follows repository commit policy,
and integrates the full delivered change range serially. Then run combined acceptance
and any review against the stable integrated candidate. An implementation packet's
completion means assigned work delivered; it does not mean the integrated feature passed.
