---
type: Task
title: Batch document type and grouping commands
description: ''
tags: []
timestamp: 2026-09-04T18:20:58Z
path:
  id: T-114
  status: complete
  effort: 8
  created: 2026-09-04
  updated: 2026-09-04
  completed: 2026-09-04
  project: path
  drafted_by: claude-opus-5
  completed_by: [claude-opus-5]
  requires: []
  implements: [F-53, F-54, F-27]
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-09-04T18:21:42Z
    result: pass
  batch: B-003
---
# Batch document type and grouping commands

## Objective

Add `Batch` as a Path document type so a set of tasks meant to be executed together can be named, ordered, and reasoned about as one unit. When this is done, `path new batch` creates a batch, `path batch add` and `path batch order` maintain its membership and sequence, and `path check` refuses a batch whose recorded sequence disagrees with the tasks that claim membership in it.

## Context

Path records tasks faithfully and says nothing about sequence. `path.requires` encodes a dependency graph that nothing traverses, and there is no way at all to say "these four tasks are one sitting's work". The absence shows up twice: choosing what to do next means reading every task file, and every small task pays a full round of completion bookkeeping on its own.

This task builds the container. The commands that make the container pay for itself are T-116 and T-117.

Batch documents live in `tasks/` as `B-NNN-slug.md`. Nothing existing has to move: `tasks.task_paths()` globs `T-*.md`, so batch files are invisible to every code path that deals in tasks.

Relevant documentation:

- [F-53, F-54 — batches](../requirements/03-functional.md#tasks)
- [F-27 — the OKF type vocabulary](../requirements/03-functional.md#okf-compliance)
- [Document conventions](../blueprints/03-conventions.md)
- [OKF mapping and the frontmatter schema](../blueprints/06-okf-mapping.md)

## Prerequisites

None. This is the first task in the group and everything else in it depends on this one.

## Scope

- A `Batch` document type: `tasks/B-NNN-slug.md`, `type: Batch`, with `path.id`, `path.created`, `path.updated`, `path.project`, `path.drafted_by`, and `path.sequence`.
- `tasks/BATCH-TEMPLATE.md`, resolved project-local first and then from the Path install, the same order `tasks._template` already uses for the task template.
- An optional `path.batch` key on tasks, defaulting to nothing, naming at most one batch.
- `B-NNN` identifier allocation sharing the never-reuse rule already implemented for `T-NNN`, by generalising `next_id` and `_referenced_ids` to take an identifier prefix rather than growing a second copy of the search.
- `scripts/batches.py`: create, add, remove, order, membership lookup, derived status, and member rollups. Derived status is `complete` when every member is complete, `blocked` when a member is blocked and none is in progress, `in-progress` when any member is in progress, and `pending` otherwise.
- `path new batch "<title>"`, `path batch add B-NNN T-NNN...`, `path batch order B-NNN T-NNN...`.
- `check_batch` in `scripts/check.py`, wired into `run()`, which must learn to iterate `tasks/B-*.md` — no loop touches those files today, so an unchecked batch document would otherwise be the only Path document exempt from validation.
- Batch mutations rebuild `tasks/index.md`, joining `new_task` and `transition` as rebuild triggers.

### Out of Scope

- Ranking, readiness, or any notion of what to do next. That is T-116.
- `path batch start`, `path batch complete`, and batch-scoped validation reporting. That is T-117.
- The shape of the regenerated index beyond keeping it correct. That is T-119.
- Any change to `path status` output. That is T-118.

## Tasks

- [x] Generalise `next_id` and `_referenced_ids` in `scripts/tasks.py` to take an identifier prefix, keeping `T-` as the default so no caller changes.
- [x] Add `tasks/BATCH-TEMPLATE.md` with a fully-keyed, blank frontmatter skeleton and a body carrying Goal, Why These Together, and Sequence sections.
- [x] Write `scripts/batches.py` with create, add, remove, order, membership, derived status, and rollups.
- [x] Add `path.batch` to `tasks/TASK-TEMPLATE.md` and to `new_task`, with a `--batch` option on `path new task`.
- [x] Add `Batch` to the type vocabulary in `blueprints/06-okf-mapping.md` and document the batch schema there.
- [x] Add `cmd_new_batch` and `cmd_batch` to `bin/path` with subparsers taking `--path`.
- [x] Add `check_batch` to `scripts/check.py` and teach `run()` to iterate `tasks/B-*.md`.
- [x] Make batch mutations rebuild the tasks index.
- [x] Write `tests/test_batches.py`, seeding each defect before asserting the check finds it.

## Acceptance Criteria

- [x] `path new batch "<title>"` creates `tasks/B-NNN-slug.md` with valid frontmatter and no placeholder markers left in required fields.
- [x] `path batch add B-NNN T-NNN` sets `path.batch` on the task and appends the id to the batch's `path.sequence`, and both files are written by the tooling rather than by hand.
- [x] `path batch order B-NNN T-002 T-001` rewrites `path.sequence` in the given order and refuses an ordering that omits or invents a member.
- [x] A batch identifier that any document refers to is never reused, on the same evidence `T-NNN` allocation uses.
- [x] Batch status and completion date are computed on read and appear nowhere in any file on disk.
- [x] `path check` fails a batch whose `path.sequence` does not name exactly the tasks whose `path.batch` points at it, and fails a task whose `path.batch` names a batch that does not exist.
- [x] A task with no batch is unaffected: it validates, and nothing about it changes.

## Validation

- [x] A batch whose `sequence` omits a task that claims membership is seen to fail `path check`, for that reason.
- [x] A batch whose `sequence` names a non-existent task is seen to fail, for that reason.
- [x] A task whose `path.batch` names a non-existent batch is seen to fail, for that reason.
- [x] Derived status is unit-tested from hand-built member rows across all four outcomes, including the blocked-with-none-in-progress case.
- [x] Identifier allocation is tested against a deleted batch whose id survives only in a build log entry.
- [x] A false-positive guard: an unbatched task with an empty `requires` still passes `path check` unchanged.
- [x] `python3 -m unittest discover -s tests`, `ruff check scripts/ bin/path tests/`, and `./bin/path check` all pass.

## Notes

The two design choices worth defending, both following existing precedent rather than inventing anything:

Batch status is derived, never stored. F-31 already forbids storing a decision's age for exactly this reason — a computed value written to disk is a second copy, and a second copy is a thing that drifts. The same argument retires `completed` on a batch, which is only `max(member.completed)`.

Membership lives on the task and ordering lives on the batch, which does put the member set in two places. The resolution is that `path.sequence` is regenerated by the commands rather than authored, and `check_batch` fails when the two disagree — so the drift is not merely discouraged, it cannot be committed.

Putting batch files in `tasks/` rather than a new folder is deliberate: no fifth document directory, no second index, and the existing `T-*.md` glob already excludes them from every task code path.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*
