# Fanout workflow delivery evidence

Implemented and installed on 14 September 2026. The four workflow recipes share native
harness adapters and use independently configurable model rosters. Plain fanout keeps
its version-3 interface; workflows emit version 4. See the
[usage guide](../skills/fanout/references/workflows.md) and
[accepted design](plans/fanout-workflows.md).

## Automated acceptance

`tools/quality/bin/quality check` completed successfully, including **89 fanout tests**
(26.173 seconds for that suite). The run log is `/tmp/workflow-quality.log`.
Relevant lint/format checks, Node syntax validation, and `git diff --check` passed.
No new dependency was added.

The tests exercise native subprocess boundaries, rather than only recipe construction:

- Mixed Agy/Pi/Muse/Claude dispatch shares a concurrency cap. A synthetic future route
  participates in both dispatch and required completion using configuration alone.
- Roster replacement, removal, explicit-file precedence, unchanged other defaults,
  malformed/empty/duplicate configuration, missing executables, and incompatible flags.
- Describe makes no launches or output directories. Invalid, blocked, nonzero, oversized,
  timed-out, and quota-failed replies do not become successful coverage. Input mutation
  invalidates review completion. SIGTERM cleans up worker processes and their children.
- Direct workflow payloads and legacy plain receipts remain separate explicit contracts.
  A valid large incremental stream is accepted by the workflow default; an explicitly
  smaller output limit still rejects it. Critique permits empty feedback lists.
- Real temporary Git checkouts deliver two disjoint committed changes. Caller integration
  runs a combined check, including a negative case where individually passing work fails
  combined acceptance. Overlap, duplicate checkouts, dirty starts, missing prerequisites,
  unknown members, symlinks, and unsupported write profiles are rejected. An out-of-scope
  untracked edit is retained and marked nonconforming.
- The real installer runs twice in a temporary Codex home, includes the complete workflow
  package, and preserves user roster configuration. The live Codex copy was refreshed
  through `bash scripts/install.sh codex`; its `--check` comparison passed.

## Bounded live qualification

Trial artifacts are retained in this temporary directory (not committed source):

`/var/folders/sp/gftbmpy17y1_q_6cp75p8gm40000gn/T/fanout-workflows-live-d65x_0gt`

Each named run below contains `packet.json`, resolved configuration, input identities,
and native attempt files. Successful replacement rosters were explicitly selected test
configuration files; the runner never substituted models or silently edited starters.

| Final receipt trial | Valid / requested | Elapsed | Native reported cost | Result |
| --- | --- | --- | --- | --- |
| `review-plan-direct` | 1 / 2 | 120.135 s | $0.003589, partial | OpenCode DeepSeek valid; Agy quota timeout |
| `review-available-direct` | 1 / 2 | 49.484 s | $0.583377, partial | Claude Fable valid; OpenCode malformed JSON |
| `bug-hunt-direct` | 2 / 2 | 33.316 s | $0.553500 | Fable + Pi DeepSeek completed |
| `critique-direct` | 3 / 3 | 59.562 s | $0.834526 | Fable + Pi DeepSeek + Sonnet completed |
| `implement-direct` | 2 / 2 | 29.397 s | $0.199979 | Pi DeepSeek + Sonnet delivered owned changes |

These costs are native estimates for the individual runs, not the total cost of development
or a billing guarantee. Tokens and costs can be partial; the packet records that explicitly.
Claude metadata includes auxiliary Haiku usage as well as the requested primary model.

### Plan review

The supplied plan said to retry every error indefinitely, allow repeating a charge-card
POST, and test only one successful request. The task required termination, cancellation,
and no duplicate charge, and stated that the API supports idempotency keys.

Valid final-format reports identified the seeded missing retry bounds/error classification,
stable idempotency, cancellation, and failure-path tests. Claude also surfaced missing API
semantics and language/context instead of inventing a concrete implementation. Source
inputs remained unchanged. Additional suggestions require caller judgment; this trial
establishes useful review evidence, not universal correctness of every recommendation.

An earlier `review` run returned 2/2 reports from Agy Gemini 3.8 Flash High and Claude Fable
in 56.693 seconds, before the final direct-payload receipt change. It therefore does not
qualify Agy's final receipt format. Subsequent Agy runs hit account quota (429); final native
schema forwarding is fixture-tested but live qualification of that format remains limited
by quota. The runner preserves the native quota reason. OpenCode returned one valid final
receipt and later failed JSON parsing at position 9939. Both partial runs stayed incomplete.

A one-worker plain Pi baseline (`plain-result`) timed out after 150.014 seconds with 0/1
valid reports. That provides no matched quality comparison. No speed, cost, or model-ranking
claim is justified by this small, differently configured baseline.

### Bug hunt

The seeded source had `total(values): return sum(values[:-1])`. An intentional
`average([])` ValueError was supplied as a plausible false lead. Both final investigators
reported the lost final element and declined to label the specified empty-input rejection
a bug. Independent caller execution reproduced `total([1, 2, 3]) == 3` instead of 6 and
confirmed the average behavior. No input changes were detected.

### Constructive critique consumed by the caller

The draft proposed the same faulty slice, expected 3 for `[1, 2, 3]`, and required string
rejection. Its sound choice was using the standard library with no dependencies.
The extra Sonnet critic was added through configuration alone; all three final critics
returned the same structured contract.

The caller read every report, recorded **11 accepted and 4 deferred suggestions**, and
revised the draft. Arithmetic and string-rejection corrections were accepted; additional
boolean/float/general-iterable policy was deferred where the original contract did not
specify it. The revision preserved built-in `sum` and no third-party dependencies.
Independent checks covered the expected result 6, empty/single/negative inputs, and strings
at multiple positions. No further critique round was launched.

Evidence: `critique-direct/disposition.json`, `revised-draft.md`, and `caller-checks.json`.
This qualifies feedback consumption and revision, beyond delivery of critic messages.

### Implementation through caller integration

Two fresh worktrees started at the same temporary repository base. Pi DeepSeek owned
`clamp.py`; Claude Sonnet owned `mean.py`. Their committed changes touched only their
assigned files and reported the assigned acceptance checks passing:

- Clamp: `800e6ca2f619b5c2e552502202009402eeed65d7`.
- Mean: `43078b26c8ca86cc40e1438055e6218ee21b6c4d`.

The caller reviewed the source and receipts, cherry-picked each change serially into a
separate integration worktree, and independently verified:

```python
assert mean(clamp(v, 0, 10) for v in [-5, 5, 15]) == 5
assert mean(iter([1, 2, 3])) == 2
# clamp(0, 10, 0) and mean([]) both raise ValueError.
```

Integrated HEAD: `c6e756945c322bfdb9c6e37a7bcacddc4277a18b`.
`implement-direct/integration.json` records the exact combined check and exit code 0.
Fanout itself still reports assigned delivery with integration/verification pending;
the caller supplied that final evidence. No external worker pushed changes.

## Changes driven by live results and limits

The initial workflow prototype wrapped payload JSON in a string. Live models sometimes
double-escaped it or produced prose. Final workflow receipts use a direct object with
native schema support where available; plain receipts are unchanged. This is an explicit
new contract, not a heuristic decoder for malformed model responses.

A valid Pi critique generated 1.62 MB of incremental events and exceeded the old plain
1 MB threshold. Workflow mode now defaults to 8 MB; explicit limits are still enforced.
This is a post-capture acceptance threshold, not a streaming disk quota.

No live Muse workflow trial was performed; mixed native fixture coverage exercises its
workflow parser and dispatch. Agy quota and intermittent OpenCode malformed output remain
provider qualification limits. The feature retains partial evidence and reports failures
honestly; it cannot guarantee a provider will return a valid report on every attempt.

Ownership and review checks compare filesystem endpoints. They are not an OS sandbox and
cannot detect every reverted transient edit, Git metadata change, or external side effect.
Worktree preparation, claim verification, integration, and final acceptance remain caller
responsibilities. No automatic repair/critique loop, paid judge, model substitution, or
cross-provider spending cap was introduced.
