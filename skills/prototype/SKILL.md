---
name: prototype
description: Resolve a specific design uncertainty with a small runnable experiment. Use when explicitly asked to use prototype; producing a prototype does not authorize production integration.
---

# Prototype

Build and run the smallest experiment that can inform the user's decision. The deliverable is
evidence and a recommendation, with a runnable artifact where useful.

- State the uncertainty, the decision it affects, and the observation that would favor or reject
  the approach. Set a proportionate scope and stopping point from the request. Ask only when a
  missing constraint would materially change the experiment.
- Inspect relevant contracts and the existing implementation. Start with a realistic caller
  example or user interaction when evaluating an interface; derive the implementation from it.
- Use the current approach as a baseline when making comparative claims. Build multiple options
  only when they represent meaningful alternatives; one experiment can resolve the question.
- Choose a scratch location or a narrowly scoped change in the authorized checkout. Keep the
  artifact identifiable and preserve existing work. Do not create a worktree or delegate unless
  authorized. Avoid introducing a framework or dependency solely to host the experiment.
- Run the behavior that answers the question. For APIs, execute the caller example; for UI,
  exercise the actual interaction and capture relevant visual evidence; for performance,
  compare under equivalent conditions using the project's measurement tools. Mocks and reduced
  inputs can isolate a question, but state what they cannot establish about the real system.
- Revise the experiment when a result exposes a relevant flaw, within its agreed scope. Stop
  when the decision is supported, the bound is reached, or required evidence is unavailable.
  An inconclusive result is valid; do not expand into a production implementation to force one.

Report the decision, observations, limitations, artifact location, and exact way to rerun it.
Recommend keeping, revising, or discarding the approach. Identify shortcuts that would need work
before integration. Retain useful artifacts for review unless cleanup was requested; remove only
disposable task-created files. Follow repository policy for commits, keeping prototype status
clear. Production integration requires authorization beyond the prototype request; honor any
such authorization already given.
