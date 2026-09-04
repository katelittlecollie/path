---
type: Task
title: Batch-scoped bookkeeping
description: ''
tags: []
timestamp: 2026-09-04T18:22:27Z
path:
  id: T-117
  status: complete
  effort: 8
  created: 2026-09-04
  updated: 2026-09-04
  completed: 2026-09-04
  project: path
  drafted_by: claude-opus-5
  completed_by: [claude-opus-5]
  requires: [T-114]
  implements: [F-59]
  change_log: []
  drift_log:
  - date: 2026-09-04
    kind: post-completion-bug
    effort_to_correct: 1
    note: close.current_task greps the Current Task line for the first T-NNN, so a line naming a batch and its members reported a completed member as current. Found by running path close after B-003.
  issues: []
  proof:
    checked_at: 2026-09-04T18:21:42Z
    result: pass
  batch: B-003
---
# Batch-scoped bookkeeping

## Objective

Make the completion ceremony cost one round per batch rather than one round per task. When this is done, `path batch start` and `path batch complete` move a batch's members in one call, `path check B-NNN` validates every member to the same standard as validating them individually, and `path new retrospective` scaffolds the one artefact the process requires and has no command behind.

## Context

Completing a task requires a hand-written `RETROSPECTIVE` build log entry naming it in `path.related_tasks`, a `path check` run, an `AGENTS.md` update, and a pass through the Definition of Done. On a one- or two-point task that ceremony is most of the work, and it is why small tasks drag the delivery rate rather than raising it.

Most of the fix is already legal. `check_retrospective` reads `path.related_tasks` as a list, so a single entry naming four tasks already closes all four. What is missing is tooling that makes the batch-shaped path the easy one instead of a thing you have to know.

The retrospective scaffold is the largest single cut, and it is squarely on the deterministic side of Path's line: filling in a list of identifiers is fact, and it is exactly where the T-030 defect lived — an entry that named a task in prose but not in the field the checker reads. The prose stays a template for a person or an agent to write.

Relevant documentation:

- [F-59 — batch-scoped operations](../requirements/03-functional.md#tooling)
- [F-41, F-42 — proof of done](../requirements/03-functional.md#proof-of-done)
- [Definition of Done](../blueprints/05-definition-of-done.md)
- [Architecture — the CLI as the deterministic layer](../blueprints/01-architecture.md)

## Prerequisites

T-114, for the batch document type. Recorded in `path.requires`.

## Scope

- `path batch start B-NNN`: every pending member becomes in-progress, in one call, through the existing `tasks.transition` so the transition table stays the single authority.
- `path batch complete B-NNN`: every in-progress member becomes complete. It refuses, naming the offender, when a member is in any other status — completing a task that was never started is precisely what the transition table exists to prevent, and a batch command must not become a way around it.
- `path check B-NNN`: runs the existing per-task checks across every member plus the batch document checks, and reports once. Proof is recorded on each member that passes, reusing `_record_proof`.
- `path new retrospective --for B-NNN`, also accepting repeated `--for T-NNN`: writes `build-log/YYYY-MM-DD-<slug>.md` with `type: Build Log Entry`, `path.entry_type: RETROSPECTIVE`, and `path.related_tasks` filled from the batch's members, then rebuilds the build-log index.
- Same-day filename collisions resolved with the existing `-2`, `-3` suffix convention.

### Out of Scope

- Changing what `check_retrospective` requires. One entry naming every member is already sufficient and no rule needs relaxing.
- Making `path close` batch-aware. Its `AGENTS.md` scrape is verified to still work and is otherwise untouched.
- Writing any retrospective prose. The command scaffolds; the judgment stays with whoever writes it.

## Tasks

- [x] Add `start` and `complete` to `path batch`, delegating each member to `tasks.transition`.
- [x] Make `path batch complete` refuse a batch with a member in the wrong status, naming that member.
- [x] Extend `check.run` to accept a batch identifier and validate every member plus the batch document.
- [x] Record proof on each member that passes, and on none when the batch fails.
- [x] Add `path new retrospective` with repeatable `--for` accepting task and batch identifiers.
- [x] Rebuild the build-log index after writing a retrospective.
- [x] Extend `tests/test_batches.py` and `tests/test_check.py` for the batch-scoped paths.

## Acceptance Criteria

- [x] `path batch start` moves every pending member to in-progress and leaves members in other statuses alone.
- [x] `path batch complete` moves every in-progress member to complete and stamps each `path.completed`.
- [x] `path batch complete` refuses, naming the member, when any member is pending or blocked, and changes nothing when it refuses.
- [x] `path check B-NNN` reports the same findings that checking each member individually would, in one run, and exits non-zero if any member fails.
- [x] Proof is written on passing members only, and never when the run failed — matching the existing rule that a failing check records nothing.
- [x] `path new retrospective --for B-NNN` produces an entry that `check_retrospective` accepts for every member of that batch.
- [x] The generated entry parses as OKF and leaves no placeholder marker that `path check` rejects.
- [x] A same-day second retrospective does not overwrite the first.

## Validation

- [x] `path batch complete` on a batch with one pending member is seen to fail, naming that member, with no file modified.
- [x] A partially-failing batch is seen to exit non-zero and to leave `path.proof` unwritten on every member, including the ones that passed.
- [x] A generated retrospective is seen to satisfy `check_retrospective` for each member, and a hand-made entry naming a task only in prose is still seen to fail — the T-030 regression stays covered.
- [x] Two retrospectives written on the same day are seen to produce two files.
- [x] `path batch start` on a batch with an already in-progress member is seen to leave that member untouched rather than raising.
- [x] `path close` is run and its `AGENTS.md` scrape confirmed still to work.
- [x] `python3 -m unittest discover -s tests`, `ruff check scripts/ bin/path tests/`, and `./bin/path check` all pass.

## Notes

The refusal in `path batch complete` is the part to get right. A batch command that quietly completed a pending member would make "in progress" meaningless and leave the burn-up with no interval to measure — the exact reasoning behind the transition table in `scripts/tasks.py`. Reducing ceremony is the goal; reducing rigour is not, and the difference is that every rule still applies, it just applies once.

Delegating to `tasks.transition` rather than writing statuses directly is what keeps that true. There should be no second place in the codebase that knows which transitions are legal.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*
