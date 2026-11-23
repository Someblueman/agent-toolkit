---
name: ambition-check
description: Check that the user is asking for the right thing before starting substantial work. Climb one rung up from the literal ask to the outcome it serves, and turn that outcome into measurable success criteria. A hook triggers it on the first prompt of each session. Also use it when the user types /ambition-check or asks to clarify or sharpen a request, or when a new request in the session is large and vague.
---

# Ambition check

The point is to make sure the work aims at the outcome the user actually wants, stated so that
"done" can be checked. It is not a questionnaire. Most of the time it should cost the user one
answer or nothing.

## 1. Decide whether it applies

Skip the check, and just do the task, when the prompt is any of these:
- a question, explanation or lookup
- a small, concrete task ("rename X to Y", "fix this typo", "run the tests")
- a continuation of earlier work ("carry on", "now push it")
- already specific, with a clear measure of success

When you skip, don't mention the check. It applies to requests that are broad ("speed up the
codebase"), open-ended ("build this feature", "clean this up") or that only name an activity
("look into the flaky tests").

## 2. Climb one rung

Ask what the request is in service of. Name the outcome behind the literal ask, then check whether
the ask is the best route to it.
- "Speed up the codebase" might mean higher throughput, lower latency at the tail, less memory
  (RSS), faster startup, or faster builds and CI. These lead to different work.
- "Build this feature" serves some user or business outcome. Find out who uses it and what they
  can do afterwards that they couldn't before.
- "Fix the flaky tests" might really mean "make CI trustworthy again", which could mean
  quarantining tests rather than fixing them.

Look at the code and context first (recent commits, issues, benchmarks, TODOs), so that your
suggested outcomes are grounded in this project rather than generic.

## 3. Make it measurable

Turn the outcome into one to three success criteria. Each names:
- the metric or binary check (p95 latency, peak RSS, a test that must pass, a user-visible
  behaviour)
- how it is measured (command, benchmark, environment, number of runs)
- the target or threshold, plus the baseline if you can get it cheaply
- scope limits, if they matter (what not to touch)

Prefer honest binary checks over invented numbers. If no metric fits, say what evidence will show
the work is done.

## 4. Confirm with the user, or proceed

- **If the outcome is genuinely ambiguous** and the options lead to different work, ask once with
  AskUserQuestion: two to four concrete readings, your recommended one first, each with its
  success criterion. Combine questions into that one round. Don't follow up with more rounds.
- **If one reading is clearly most likely**, don't ask. State the goal and the criteria in two or
  three lines and start, so the user can redirect you.
- **If you cannot ask** (a non-interactive or headless run), state your assumed goal and criteria
  and proceed.

## 5. Use the criteria

- Treat the agreed criteria as the definition of done for this task. Include them in every brief
  you give subagents or Sol.
- Measure the baseline before changing anything when the criteria are numeric.
- In the final report, say how the result measures against each criterion, including any that
  were missed.
