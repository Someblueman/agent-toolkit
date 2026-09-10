---
name: investigate
description: Investigate a question or bug using code, runtime evidence, and relevant history. Use when explicitly asked to use investigate; findings do not authorize fixes.
---

# Investigate

Answer the user's question with evidence and explain what remains uncertain. Keep the work
read-only unless the user separately authorizes changes.

- Restate the question briefly when ambiguity could change the investigation. Separate the
  reported symptom from any suggested cause; treat both user and agent hypotheses as hypotheses.
- Trace the smallest relevant execution path from input to observable outcome. Explain the
  important state transitions, ownership, and failure boundaries, with source locations.
- Use existing tests, logs, and safe reproductions to distinguish plausible causes. Check what
  a command writes or triggers before running it; do not alter project files, start a costly
  campaign, or affect external systems merely to gather evidence. Report a needed experiment
  when it exceeds the authorized scope.
- Consult Git history, review discussions, documentation, or previous conversations when intent
  or earlier attempts matter. Verify historical claims against current code. Do not infer the
  author's motivation from implementation alone or search every available source by default.
- For each material conclusion, connect the claim to an observation and explain its limits.
  Keep observed behavior, documented rationale, and inferred causes distinct. A passing test
  or failure to reproduce does not by itself rule out the reported bug.
- Stop when the question is answered, the agreed investigation bound is reached, or further
  progress needs unavailable evidence. Prefer the next discriminating experiment over a long
  list of speculative causes.

Lead the response with the answer and confidence supported by the evidence. Include relevant
code or source links, checks performed, unresolved questions, and the next useful experiment
when needed. Scale the explanation to the question; a short trace can be enough. Do not apply
a fix or launch a prototype solely because of a finding; honor any follow-on work the user
has already authorized.
