---
type: Task
title: State-grouped tasks index
description: ''
tags: []
timestamp: 2026-09-04T18:20:58Z
path:
  id: T-119
  status: complete
  effort: 5
  created: 2026-09-04
  updated: 2026-09-04
  completed: 2026-09-04
  project: path
  drafted_by: claude-opus-5
  completed_by: [claude-opus-5]
  requires: [T-116]
  implements: [F-55]
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-09-04T18:21:42Z
    result: pass
  batch: B-003
---
# State-grouped tasks index

## Objective

Make `tasks/index.md` answer what to work on next without an agent and without a terminal. When this is done, the regenerated index groups tasks by whether they can be started, shows batches with their progress, and carries effort, batch, and unblock count on each line — so opening the file is enough.

## Context

`tasks/index.md` is regenerated wholesale from frontmatter and is the file a person actually opens, in an editor or in Obsidian. It currently lists tasks in identifier order as status and title, which tells a reader roughly what `ls` would. Solving "what is next" only in the CLI would leave the answer available to whoever is at a terminal, which is the wrong shape for a system whose premise is that its documents are readable on their own — [architecture](../blueprints/01-architecture.md) puts it as the tooling being required to write documents correctly, never to read them.

Relevant documentation:

- [F-55 — the index must group by what can be started](../requirements/03-functional.md#tasks)
- [F-26 — reserved index files](../requirements/03-functional.md#okf-compliance)
- [OKF mapping — reserved filenames](../blueprints/06-okf-mapping.md)

## Prerequisites

T-116, for readiness and ranking. Recorded in `path.requires`.

## Scope

- `okf.write_index` gains section support while still emitting no frontmatter.
- `okf.rebuild_tasks_index` emits, in this order and omitting any section that would be empty: Batches, Ready now, In progress, Waiting on prerequisites, Blocked, Complete.
- Batch lines carry derived status, task progress, and point progress. Task lines carry effort, batch where there is one, unblock count where it is non-zero, and what a waiting task waits on.
- Ready-now order is the ranking from T-116, so the file and `path next` cannot disagree.
- `_task_sort_key` generalised to any `X-NNN` prefix.
- `path batch add` and `path batch order` join `new_task` and `transition` as rebuild triggers.

### Out of Scope

- `path status`, which is T-118, and the status page, which is T-120.
- The build-log index, which is unrelated and unchanged.
- Any frontmatter on the index. OKF forbids it and nothing here adds any.

## Tasks

- [x] Add section support to `okf.write_index`.
- [x] Rewrite `okf.rebuild_tasks_index` to emit the grouped index, including batches.
- [x] Generalise `_task_sort_key` to any identifier prefix.
- [x] Make batch mutations rebuild the index.
- [x] Extend `tests/test_indexes.py`.

## Acceptance Criteria

- [x] Every file in `tasks/` appears exactly once across all sections, and no file is omitted.
- [x] The rebuilt index contains no frontmatter.
- [x] Sections that would be empty are omitted rather than printed as bare headings.
- [x] Ready-now order matches `path next` ranking.
- [x] Task lines carry effort, batch where present, and unblock count where non-zero; waiting lines name what they wait on.
- [x] Batch lines carry derived status and both task and point progress.
- [x] A rebuild is idempotent: running it twice with no change produces an identical file.
- [x] A rebuild remains a pure function of the `tasks/` directory, reading nothing outside it.
- [x] An unreadable task file is still reported to the caller rather than silently dropped.

## Validation

- [x] A task moving pending to in-progress is seen to move between sections on the next rebuild.
- [x] A project with no batches is seen to omit the Batches section entirely.
- [x] Every filename in `tasks/` is asserted present exactly once in the rebuilt index.
- [x] The rebuilt index is asserted to have no frontmatter and to still be treated as reserved by `path check`.
- [x] A second rebuild is asserted byte-identical to the first.
- [x] An unreadable task is seen to be returned in the unreadable list, preserving the behaviour that a silently incomplete index is the failure this function exists to prevent.
- [x] `python3 -m unittest discover -s tests`, `ruff check scripts/ bin/path tests/`, and `./bin/path check` all pass.

## Notes

There is a conformance judgment here worth recording rather than leaving implicit. OKF describes `index.md` as a directory listing with no frontmatter. This adds section headings to it. The reading taken is that grouping a listing does not stop it being one: no file is duplicated, none is omitted, and no frontmatter claim is introduced. T-121 records that reasoning in a decision entry, because the OKF mapping is where a future reader will go looking for it.

The property that must not be lost is that the index is a pure function of its directory. Readiness and unblock counts are computed from the tasks in `tasks/` and nothing else, so a full rebuild stays correct and self-healing — which is the whole reason these indexes are regenerated rather than appended to.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*
