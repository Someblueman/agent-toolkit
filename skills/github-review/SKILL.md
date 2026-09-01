---
name: github-review
description: Review a GitHub PR with structured, severity-tagged feedback. Load when the user asks for a PR review, diff review, or code review.
---

# GitHub PR Review

Placeholder instructions. Real guidance belongs here.

## When to load

- User says "review this PR", "review the diff", "critique this branch".
- A PR URL or `gh pr diff` output is in context.

## Behavior

1. Read the full diff.
2. Group findings by severity: blocker, major, minor, nit.
3. For each finding, cite the file and line range.
4. End with a one-paragraph summary.