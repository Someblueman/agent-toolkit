---
name: release-check
description: Pre-release sanity checks before tagging a version. Load when the user says "ready to release", "cut a release", or asks for a release checklist.
---

# Release Check

Placeholder instructions. Real guidance belongs here.

## When to load

- User says "ready to release", "cut a release", "pre-release checks".

## Behavior

1. Confirm CHANGELOG / version bump.
2. Confirm CI is green on the release branch.
3. Confirm migration notes exist for breaking changes.
4. Output a single blocker list (empty list = ready).