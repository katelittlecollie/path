---
type: Build Log Entry
title: Session close — 2026-09-04
description: B-003 and T-122 shipped; two Definition of Done items not met, both documentation gaps.
tags: [session-close]
timestamp: 2026-09-04T18:44:07Z
path:
  entry_type: SESSION-CLOSE
  date: 2026-09-04
---

# SESSION-CLOSE — 2026-09-04

## Completed This Session

One batch of eight, plus one follow-up task.

- **T-114** — `Batch` document type at `tasks/B-NNN-*.md`, `path new batch`, `path batch add|remove|order`, `B-NNN` identifier allocation through the existing never-reuse search, and `check_batch`.
- **T-115** — `velocity` and `forecast` in `scripts/metrics.py`: points per week over a trailing fourteen days, projected against the remaining backlog, refusing to produce a number below two completions and never widening the window to find data.
- **T-116** — `scripts/next.py`: readiness, unblock counts, ranking, and the `path next` command with `--batch` and `--json`.
- **T-117** — `path batch start|complete`, `path check B-NNN`, and `path new retrospective --for`, which fills in the `path.related_tasks` field the checker reads.
- **T-118** — `path status` rewritten around readiness: ready-now and waiting-on-prerequisites as separate sections, batches, backlog, rate, forecast.
- **T-119** — `tasks/index.md` regenerated grouped by state, so the file answers "what can I start" without running anything.
- **T-120** — forecast banner and backlog board on `status.html`, above the charts.
- **T-121** — requirements F-53 to F-59, batch conventions, the `Batch` schema and `yq` invocations, the architecture amendment, and the Definition of Done's mechanical surface.
- **T-122** — rotated the colliding date labels on the status page's three charts. Reported by a human looking at the page; no gate on this project could have caught it.

## Current Task

T-122

## Mechanical Definition of Done Check

Run automatically by `path close` via `path check` — see blueprints/05-definition-of-done.md for what this does and does not cover.

```
ok — every check passed.
```

Also green outside `path check`: 503 tests via `python3 -m unittest discover -s tests`, and `ruff check scripts/ bin/path tests/`.

## Judgment Definition of Done Review

Worked through for every task completed this session. Two items are **not met** and are carried into the recommendations below; the rest are met.

- [x] Every acceptance criterion is not merely checked off but actually met and verifiable — the box being ticked is a claim, not proof.
- [x] Any code created achieves the project's required level of code coverage and all tests pass. 503 tests pass, up from 353. This project sets no coverage threshold, so "required level" is vacuous here rather than satisfied; every new module arrived with its own test file.
- [x] The work has been reviewed by a human being. Confirmed by the project owner at close.
- [ ] **Not met.** All files created or modified are in the correct location per the project's folder structure blueprint. `blueprints/02-folder-structure.md` does not mention batches at all — its `tasks/` listing names only `index.md`, `TASK-TEMPLATE.md`, and `T-NNN-*.md`. `tasks/B-NNN-*.md` and `tasks/BATCH-TEMPLATE.md` are therefore in a location the blueprint does not describe. The location is right; the blueprint is behind it.
- [x] File and directory names follow the naming conventions in `blueprints/02-folder-structure.md`. `B-NNN-[short-slug].md` mirrors the task rule exactly.
- [x] All new code passes a linting check appropriate for the project without errors.
- [x] All new code compiles (or parses) without errors.
- [x] All code changes, including the task itself, have been checked in to a git-based repo with a descriptive commit message.
- [x] The work is consistent with the architecture described in the project's blueprints — after the amendment. Before it, `blueprints/01-architecture.md` said Path does not track velocity, which T-115 made false; that is what T-121 existed to correct rather than let stand.
- [x] Any deviations from the blueprints are intentional and documented in the build log. Both are in [the decision](./2026-09-04-forecasting-the-backlog.md): forecasting the backlog, and giving a reserved `index.md` section headings.
- [x] The work does not otherwise break or contradict anything established in prior completed tasks. Every pre-existing test still passes; the three that changed are recorded below.
- [x] If any new requirements were discovered during execution, they are documented. F-53 through F-59, plus `Batch` added to F-27's vocabulary and the sequence-membership check to F-41's enumeration.
- [ ] **Partially met.** If any blueprint decisions were made or changed during execution, the relevant blueprint file has been updated and a `CHANGE` entry written in the build log. Four blueprints were updated and no entry of type `CHANGE` was written. The substance is recorded — the reversal in a `DECISION` entry, the rest under "What Changed in the Documents" in the batch retrospective — but the log carries no entry of the type this item names, and the four existing convention changes in this repository all used one.
- [x] `AGENTS.md` actually reflects the completed task and points at the next pending one, if any. Current Task names T-122; there is no pending task to point at.
- [x] A human developer with no prior context could read the delivered files and understand what was built.
- [x] The project is in a coherent, consistent state — not left mid-task or in a transitional condition.

## State at Close

Working, and self-hosting on the feature it just built. Fourteen tasks, all complete;
69 of 69 points; no open decisions; no pending task. B-003 is the repository's first
batch and closed with one retrospective covering all eight members, which is the
claim the batch feature exists to make.

Three tests changed rather than being added, all deliberately:
`tests/test_status.py` now expects a task's recorded `title` where it previously
expected a lowercased filename slug, and `tests/test_indexes.py` asserts which
section a task is filed under where it previously expected an inline status word.

One defect was found and fixed within the session: `close.current_task` grepped the
Current Task line for the first `T-NNN`, so a line naming a batch and its members
reported a finished member as the work in hand. Logged as post-completion drift
against T-117, fixed, and the regression test was observed failing for its own reason
before it passed.

## Next Session — Start Here

Two documentation gaps from the review above, in this order:

1. Add batches to `blueprints/02-folder-structure.md` — `tasks/B-NNN-[short-slug].md` and `tasks/BATCH-TEMPLATE.md` in the `tasks/` listing, and a line in the prose saying batch documents live alongside the tasks they group. Roughly 1 point.
2. Decide whether the missing `CHANGE` entry needs writing, or whether the `DECISION` entry plus the batch retrospective already satisfy it and the Definition of Done's wording is what should change. This is a judgment about the convention, not a gap to paper over.

Both are small enough to be one batch. Neither blocks anything.

## Blockers / Open Questions

None blocking.

One open question, from item two above: whether a `CHANGE` entry is required when a
`DECISION` entry already records the same blueprint change in more detail. The
Definition of Done reads as though it is; the four existing `CHANGE` entries in this
log were all changes with no accompanying decision, so the case has never come up.

## Process Improvement Recommendations

`path close` reported "No issues were logged this session", and that is true of
`path.issues` and misleading about the session. Four things are worth recording.

**1. A post-completion drift entry never reaches this review.** `close.tasks_with_issues`
reads `path.issues` only, so the T-117 defect — logged correctly as
`path log drift --kind post-completion-bug` — is invisible here. That is the one
category most likely to reveal a documentation gap, since by definition something got
past every check. *Recommendation:* `scripts/close.py` should feed `drift_log`
entries of kind `post-completion-bug` into the Process Improvement section alongside
`path.issues`. This is a code change to Path and needs its own task; naming it here
rather than acting on it.

**2. `blueprints/02-folder-structure.md` was not updated when a new document type
landed.** The gap that let it through is that nothing connects "a new `type:` value"
to "the folder-structure blueprint lists where it lives". T-114's task list named the
OKF mapping and the conventions blueprint and not this one, and no check covers it —
index files are reserved and carry no claim to validate. *Recommendation:* update the
blueprint, and consider whether the Definition of Ready should ask, for any task
introducing a document type, which blueprints describe where documents live.

**3. Nothing on this project looks at rendered output.** T-122's collision passed 503
tests, ruff, and `path check`, and reached the project owner by being looked at. This
is a real limit of the mechanical half rather than a defect in it. *Recommendation:*
none yet — one report is an anecdote, and adding a checklist item on the strength of
one is how checklists stop being read. Worth a `[Judgment]` line if it recurs.

**4. This session produced four `SESSION-CLOSE` entries for one session.** Entries
`-1` through `-3` are empty scaffolds, written by running `path close` as a
verification step while building T-117 and T-120, and they are committed. They make
the log claim four sessions happened. *Recommendation:* delete the three empty ones —
they record nothing and F-22's "written at the time of the event" does not protect an
artifact of testing the command. Left in place pending the owner's decision, since
they are already in history.
