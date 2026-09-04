---
type: Task
title: Readiness ranking and the next-work command
description: ''
tags: []
timestamp: 2026-09-04T18:20:58Z
path:
  id: T-116
  status: complete
  effort: 8
  created: 2026-09-04
  updated: 2026-09-04
  completed: 2026-09-04
  project: path
  drafted_by: claude-opus-5
  completed_by: [claude-opus-5]
  requires: [T-114]
  implements: [F-58]
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-09-04T18:21:42Z
    result: pass
  batch: B-003
---
# Readiness ranking and the next-work command

## Objective

Make "what should I work on next" a single cheap question. When this is done, a task is readable as ready or not from frontmatter alone, ready tasks are ranked by a stated rule, and `path next` names the next task — or the next batch — in enough detail to start cold, without the caller opening every task file.

## Context

`path status` already has a "Next up" block, and it is pending tasks sorted by identifier. It never consults `path.requires`, so a task it names may be unstartable, and a reader cannot tell which. The practical consequence is that picking work means having an agent read the whole `tasks/` directory — spending tokens to rediscover something already recorded in frontmatter.

Readiness is not a new fact. It is `path.status` and `path.requires`, which `path check` already validates and nothing else consults.

Relevant documentation:

- [F-58 — readiness and the next-work command](../requirements/03-functional.md#tooling)
- [F-32 — every metric derivable from frontmatter alone](../requirements/03-functional.md#metrics)
- [Architecture — the CLI as the deterministic layer](../blueprints/01-architecture.md)

## Prerequisites

T-114, for batch membership and sequence. Recorded in `path.requires`, where `path check` enforces it.

## Scope

- `scripts/next.py`, taking row lists rather than paths so it tests with hand-built dicts.
- Readiness: a task is ready when its status is `pending` and every identifier in `path.requires` names a complete task. Pending tasks failing that are waiting on prerequisites, which is a different thing from `status: blocked` and must be reported separately.
- Unblock counts: for each task, how many other tasks name it in `requires`.
- Ranking, in order: members of an in-progress batch in that batch's sequence order; then descending unblock count; then ascending identifier.
- `path next` printing the top-ranked ready task with its identifier, title, effort, batch, file path, implemented requirements, and what it unblocks.
- `path next --batch` printing the next ready batch with its members in sequence order, each marked ready or waiting with what it waits on.
- `--json` for both.
- When nothing is ready, exit zero with a message naming what blocks the closest candidate — a queue that is legitimately empty is not an error.
- `readiness` added to `metrics.build()`, so the same computation feeds the index and the status page rather than being reimplemented by each.

### Out of Scope

- `path status` output, which is T-118.
- The regenerated index, which is T-119.
- The status page, which is T-120.
- Any change to how `requires` is validated. That already works.

## Tasks

- [x] Write `scripts/next.py` with readiness, unblock counts, and the ranking rule.
- [x] Add `readiness` to `metrics.build()` so one computation serves every consumer.
- [x] Add `cmd_next` to `bin/path` with `--batch`, `--json`, and `--path`.
- [x] Handle the empty queue by naming the closest blocker.
- [x] Write `tests/test_next.py` from hand-built rows.

## Acceptance Criteria

- [x] A pending task with an incomplete prerequisite is never returned by `path next` and appears under waiting, naming what it waits on.
- [x] A pending task with no prerequisites, or with all of them complete, is ready.
- [x] `status: blocked` is reported separately from waiting on prerequisites, and neither is presented as the other.
- [x] Ranking puts a member of an in-progress batch first, in that batch's sequence order.
- [x] Absent an in-progress batch, the task unblocking the most others comes first, and ties break by ascending identifier.
- [x] `path next` output is sufficient to start the task cold: it names the file to open.
- [x] `path next --batch` lists members in sequence order with per-member readiness.
- [x] An empty ready queue exits zero and names what is blocking the closest candidate.
- [x] Every figure is derivable from frontmatter with a documented `yq` invocation.

## Validation

- [x] A graph whose lowest-identifier pending task is blocked by an incomplete prerequisite is seen to exclude it — the case the current identifier sort gets wrong.
- [x] A task whose prerequisite is `in-progress` rather than `complete` is seen to be waiting, not ready.
- [x] Ranking is tested where batch order and unblock count disagree, asserting batch order wins.
- [x] Tie-breaking by identifier is tested with two tasks of equal unblock count.
- [x] An entirely blocked backlog is seen to exit zero with a message, not to raise.
- [x] A cyclic `requires` pair is seen to be reported rather than looping forever.
- [x] A false-positive guard: an unbatched task with an empty `requires` still appears as ready.
- [x] `python3 -m unittest discover -s tests`, `ruff check scripts/ bin/path tests/`, and `./bin/path check` all pass.

## Notes

Waiting on prerequisites and `status: blocked` look similar and mean opposite things. The first is a fact derived from the graph and resolves itself when the prerequisite completes. The second is a human declaring an obstacle, and resolves only when a person acts. Collapsing them would hide real blockers inside a list that mostly clears on its own.

Ranking by unblock count is a claim worth stating: finishing the task that frees the most other work first is a heuristic, not a law, and it is deterministic and explainable, which is the property that matters here. The batch override exists because a batch is an explicit human judgment about order, and an explicit judgment outranks a computed heuristic.

A cycle in `requires` is possible to write and `path check` does not currently reject one. This task must not hang on it. Detecting and reporting it is enough; rejecting it is a separate question.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*
