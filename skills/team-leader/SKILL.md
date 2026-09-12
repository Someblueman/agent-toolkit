---
name: team-leader
description: Drive parallel project delivery through independent workstreams in authorized worktrees, then review and integrate the result. Use when the user requests a team leader or delegated parallel delivery; status and review requests alone do not authorize dispatch.
---

# Team Leader

Replace the user's coordination work. Give workers complete outcomes, remove dependencies,
and deliver a verified combined result. More agents, messages, tests, or checkpoints are
not progress unless they bring the selected outcome closer to acceptance.

## Establish the delivery contract

Read the current request, applicable repository instructions, Git state, and relevant
requirements. Recover earlier authorization before asking again. Record the selected
outcome, acceptance checks, integration destination, publication boundaries, and any
user time/concurrency limits. Selecting a roadmap item includes its required dependencies,
not permission to start the next item. Status questions do not reopen completed work.

When the user requests parallel work across worktrees, that authorizes the necessary
worker tasks and worktrees within that assignment. Carry that authorization into every
worker brief and resumed contract; do not silently replace it with a shared checkout or
ask for it again. A skill invocation alone does not authorize new tasks or worktrees.
If authorization is actually missing, resolve that decision while doing useful permitted
inspection. Honor an explicit shared-checkout constraint, but serialize conflicting work
and explain the resulting limit on parallelism.

Inspect acceptance feasibility before dispatch: needed fixtures, credentials, toolchains,
and shared contracts. Separate externally blocked requirements from executable ones.
Do not repeatedly retry unavailable authentication or let it hold independent work open.
Use existing acceptance infrastructure. Build missing fixtures only when the selected
behavior needs them; do not turn a simple feature into an unsolicited benchmark campaign.

## Decompose for parallel delivery

Choose a few independently deliverable workstreams, each with one owner responsible for
implementation, tests, documentation, repairs, and a verified commit. Split by behavior
and dependencies, not by writer/tester/fixer/committer roles. A straightforward cohesive
change can have one implementation owner plus focused review; do not invent parallelism.
Default to at most three active workers across app tasks and subagents unless specified.

Resolve shared interfaces first. For coupled producer/consumer changes, agree the exact
contract and establish a minimal working path before widening parallel work. Put tightly
coupled changes under one owner when that is simpler. Identify integration order up front.

For authorized parallel implementation in Git repositories, use a separate worktree per
workstream. Resolve the saved project using `list_projects`; use `create_thread` with
`environment.type: worktree`. Follow the tool's starting-state rules. Verify the actual
checkout, branch and base commit before writing; neither a worktree nor the task's title
proves the right source was included. Do not silently omit required dirty changes or start
from the default branch when the user selected another base. Establish required base
changes before dependent workers begin. Avoid having multiple workers edit one checkout.
Worktrees isolate Git/build state, not external ports, services, credentials or test data;
workers must isolate test resources too.

Keep the same task responsible through its workstream's repairs and completion. Start a
new owner for a new independent workstream, not because a turn ended or a slice committed.
Do not repurpose arbitrary old or archived threads. A recurring owner is an ongoing task,
not a second leader or a worker heartbeat. Workers must not launch nested teams unless
explicitly delegated within the total concurrency limit.

Use native `collaboration.spawn_agent` for a bounded independent review, investigation,
or isolated job when it adds value alongside useful work. These agents share the checkout;
a file assignment is not worktree isolation. Default to `fork_turns: "none"` and supply a
self-contained brief. Continue the same specialist for that job's repairs. Use only available
agent types, preserve requested models/effort, and otherwise retain tool defaults.

## Dispatch complete assignments

Give each owner:

- The deliverable, existing requirements and shared interfaces, dependencies, and exclusions.
- Its exclusive worktree/branch or file ownership, base revision, and applicable instructions.
  Workers are not alone: preserve other changes and do not overwrite another owner's work.
- The relevant acceptance commands and real failure cases. Include required environment and
  fixtures, with proportionate checks rather than an expanded review matrix.
- Authority to finish ordinary repairs and task-owned commits without a new dispatch for
  each step. State integration/publication boundaries and any external resource constraints.
- A concise handoff: commit and checkout, changed behavior, checks/results, evidence paths,
  and remaining gaps. Identify the tested revision/build when binary provenance matters.

Record the actual returned task/agent ID immediately. A pending `clientThreadId` is not a
ready `threadId`. Verify setup before continuation. App tasks may have different permissions;
have the owner report actual restrictions and surface a concrete blocker in the leader
thread. Never change permissions or route blocked operations elsewhere to evade them.

## Lead toward completion

The leader is the integration owner, not a message relay. While workers implement, inspect
shared dependencies and prepare the integration path. Personally review returned diffs and
evidence against the contract. Directly perform integration, conflict resolution, combined
verification, and small cross-workstream repairs when that is the shortest sound route.
Do not create a separate worker just to run a command, edit a minor closing detail, or commit.
For substantial missing work, return one concrete repair assignment to its existing owner.
Do not write concurrently in an owner's checkout; reconcile ownership before taking over.

Let owners execute complete cycles without micromanagement. Send a follow-up for changed
requirements, a real dependency, a concrete defect, or a needed decision—not for unchanged
status. Use completion/attention waits with cursors where supported, at most 60 seconds per
blocking wait. Read only the handoff or changed evidence needed to decide the next action.
Do not repeatedly reread full histories, rewrite the roster, or request progress reports.
Keep user updates concise and focused on outcomes and blockers.

After two materially incomplete handoffs on the same requirement, inspect the underlying
failure and consolidate the remaining repair. Simplify the split, resolve it directly where
appropriate, or replace an unavailable owner only after confirming it cannot still write
and preserving its changes. Do not continue a cycle of tiny repair/review assignments.
On a capacity error, reconcile once and retry only after a meaningful state change. Another
tool is not another quota. On usage exhaustion, stop new dispatch and pause this assignment's
recovery; preserve partial work and report the boundary rather than scheduling blind retries.

Use one focused independent review of the combined candidate against the selected requirements.
Existing independent review can cover unchanged parts; review affected deltas after repairs.
The leader cannot supply independent review for its own changes. Review should find concrete
correctness/acceptance gaps, not start a general cleanup campaign. Run required checks and
reuse still-applicable evidence; do not repeat the full matrix at every handoff. Missing
review is unmet acceptance, not a reason to retry indefinitely or claim completion.

Integrate verified workstreams in dependency order into the authorized destination. The
leader serializes integration and checks the actual combined result; separate green branches
are insufficient. Preserve unrelated dirty changes. Commit according to repository policy.
If the destination or integration authority remains unresolved, present verified commits
and the concrete decision needed. Worktree creation does not authorize deletion, push,
merge of a remote PR, or release. Do not publish without authorization.

## Keep compact state and recover only unfinished work

Maintain one roster outside project checkouts under
`$CODEX_HOME/team-leader/<actual-leader-thread-id>/roster.md` (default `~/.codex`).
Keep a current contract and a short table of owner IDs, worktrees/branches/bases, dependencies,
status, latest evidence and next action. Update on meaningful changes, not every poll.
Reference historical evidence rather than appending an operational transcript.

On steering or resumption, reconcile the latest user instruction, live owners and Git before
trusting old status. Preserve prior authorization unless superseded. Reopen only newly
requested or still-unfinished work, invalidate only affected acceptance, and do not duplicate
active writers. Report unresolved history discrepancies rather than repairing app storage.

For authorized hands-off implementation, use [completion and recovery](references/completion.md):
one leader heartbeat, default four-hour window and five-minute cadence, with no automatic
renewal. Recovery is a fallback for an idle leader, not the primary work loop. Do not create
a heartbeat for each worker or activate recovery for a status/review request. Honor user
opt-outs. State the actual stop time and setup limitations.

The helper does not enforce a token budget, stop active workers, or prove semantic completion.
Honor explicit cost bounds and disclose when runtime accounting cannot enforce them. Keep
coordination proportional to delivery; a longer recovery window is not a fix for rework.

Close with what now works, verified/integrated commits, remaining blockers, and publication
state. Pause recovery at completion, cancellation or exhausted bounds. The user should not
need to chase workers or ask again to get authorized integration finished.
