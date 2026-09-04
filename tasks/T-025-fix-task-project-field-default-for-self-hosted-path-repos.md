---
type: Task
title: Fix task project-field default for self-hosted Path repos
description: ''
tags: []
timestamp: 2026-07-19T17:37:05Z
path:
  id: T-025
  status: complete
  effort: 3
  created: 2026-07-19
  updated: 2026-07-19
  completed: 2026-07-19
  project: code
  drafted_by: Claude Sonnet 5
  completed_by: [Claude Sonnet 5]
  requires: []
  implements: []
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-07-19T17:37:05Z
    result: pass
---

# Fix task project-field default for self-hosted Path repos

## Objective

`new_task()` in `scripts/tasks.py` derives a task's `project` frontmatter field from `root.parent.name`, which assumes the docs root is always a nested `.path/` directory one level under the actual project. Path's own repository is self-hosted at the top level (docs root *is* the project root), so every task created here gets the wrong value — confirmed by T-024, which recorded `project: code` (the parent of `~/code/path`) instead of `project: path`. When this task is done, `new_task()` derives the project name the same way `okf.project_dir()` already does, correctly for both layouts.

## Context

Spotted in passing while building T-024, not from the backlog. `okf.project_dir(root)` (`scripts/okf.py`) already solves exactly this — nested `.path/` means the project is `root.parent`; a self-hosted root (no `.path` name) means the project *is* `root`. `metrics.py` already uses it (`okf.project_dir(root).name`) for the same purpose. `new_task()` predates that helper's use here and never got the same treatment.

Relevant documentation:

- `scripts/okf.py#project_dir` — the existing, correct layout-detection logic
- `scripts/tasks.py#new_task` (~line 191) — the bug
- `scripts/metrics.py` — the existing correct caller to match

## Prerequisites

None.

## Scope

- `new_task()`'s `project` default changed from `root.parent.name` to `okf.project_dir(root).name`.
- A regression test in `tests/test_tasks.py` covering a self-hosted-style root (no nested `.path/` — the root passed to `new_task` is the project directory itself).
- Existing nested-`.path/` test coverage continues to pass unchanged.

### Out of Scope

- Correcting the `project: code` value already recorded in T-024's and this task's own frontmatter — harmless (nothing reads it programmatically) and rewriting historical task data is not this task's job.
- Any other consumer of `root.parent.name`-style logic outside `new_task()` — none found in a search of `scripts/`.

## Tasks

- [x] Change `new_task()` in `scripts/tasks.py` to use `okf.project_dir(root).name` instead of `root.parent.name`.
- [x] Add a test to `tests/test_tasks.py` constructing a self-hosted-style root (no `.path` nesting) and asserting the correct project name.
- [x] Confirm existing `TestNewTask` cases (nested `.path/` layout) still pass unchanged.

## Acceptance Criteria

- [x] A task created with a nested `.path/`-style root gets `project` equal to the parent directory's name (existing behavior, unchanged).
- [x] A task created with a self-hosted-style root (root itself is the project directory, no `.path` nesting) gets `project` equal to that root directory's own name, not its parent's.
- [x] `python3 -m unittest discover -s tests` passes (324 tests), `ruff check scripts/ bin/path tests/` is clean.
- [x] `path check T-025` passes.

## Validation

- [x] Unit test: nested-`.path/` root — project field matches the parent directory name (regression check against existing behavior).
- [x] Unit test: self-hosted-style root — project field matches the root's own name, not the grandparent's.

## Notes

Low risk, single call site. `okf.project_dir()` already documents exactly this distinction in its own docstring, so this is applying an existing, tested rule to a caller that missed it — not inventing new logic.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*

*When complete, write a `RETROSPECTIVE` build log entry naming this task's id, and update `AGENTS.md`. `path check` verifies both.*
