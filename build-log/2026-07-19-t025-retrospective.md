---
type: Build Log Entry
title: 2026-07-19 — T-025 Retrospective
description: ''
tags: []
timestamp: 2026-07-19T00:00:00Z
path:
  date: 2026-07-19
  entry_type: RETROSPECTIVE
  related_tasks: [T-025]
---

# 2026-07-19 — T-025 Retrospective

**Type:** RETROSPECTIVE

## Summary

`new_task()` derived a task's `project` frontmatter field from `root.parent.name`, which is only correct for a consumer project's nested `<project>/.path/` layout. Path's own repository is self-hosted with its docs at the top level, so `root` there already *is* the project — `root.parent.name` resolved to the parent of `~/code/path`, i.e. `code`, for every task created in this repo. Fixed by reusing `okf.project_dir(root).name`, the same layout-aware helper `metrics.py` already used for the same purpose. One line changed in `scripts/tasks.py`; two tests added to `tests/test_tasks.py` (one confirming the existing nested-layout behavior didn't regress, one covering the previously-untested self-hosted layout).

## What Prompted This

Spotted in passing while building T-024 — that task's own frontmatter came out with `project: code` instead of `project: path`. Logged as a known, non-blocking issue in T-024's Notes rather than fixed there (would have bloated an already-scoped task), then spun off as its own follow-up.

## What Went Well

`okf.project_dir()` already existed, was already correct, and already documented the exact distinction that was missing from `new_task()` — this was a one-line fix once the right helper was found. Nothing new needed inventing.

## Effort

Estimated at 3 (one or two files, minor judgment call in choosing the test layout). Held — no drift logged.
