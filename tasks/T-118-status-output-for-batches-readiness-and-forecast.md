---
type: Task
title: Status output for batches readiness and forecast
description: ''
tags: []
timestamp: 2026-09-04T18:20:58Z
path:
  id: T-118
  status: complete
  effort: 5
  created: 2026-09-04
  updated: 2026-09-04
  completed: 2026-09-04
  project: path
  drafted_by: claude-opus-5
  completed_by: [claude-opus-5]
  requires: [T-116, T-115]
  implements: [F-55]
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-09-04T18:21:42Z
    result: pass
  batch: B-003
---
# Status output for batches, readiness, and forecast

## Objective

Make `path status` answer where the project is, what can be started, what is grouped with what, and when the backlog plausibly lands. When this is done, its queue reflects readiness rather than identifier order, batches appear with their progress, and the backlog line is followed by a rate and a projection that state the window they rest on.

## Context

`path status` today prints counts, an in-progress list, a blocked list, and a "Next up" block that is pending tasks sorted by identifier. It says nothing about whether those tasks can actually be started, nothing about grouping because grouping did not exist, and nothing about pace. Its burn-up line gives points but not position in the backlog.

Everything needed is computed by then: readiness and ranking from T-116, rate and forecast from T-115, batch rollups from T-114. This task is presentation, and it must remain presentation — `scripts/status.py` states that it is deterministic only and never invents narrative, and that stays true.

Relevant documentation:

- [F-55 — the queue must not require a terminal](../requirements/03-functional.md#tasks)
- [F-56, F-57 — rate and forecast](../requirements/03-functional.md#metrics)
- [Metrics and the status page](../blueprints/03-conventions.md)

## Prerequisites

T-116 for readiness and ranking, T-115 for rate and forecast. Both recorded in `path.requires`.

## Scope

- `queue_lines` in `scripts/status.py` becomes readiness-aware: a "Ready now" section in ranked order, and a "Waiting on prerequisites" section reporting the count and naming what the first few wait on.
- A "Batches" section listing each non-complete batch with derived status, member progress, and point progress.
- A backlog line giving tasks complete over total and points complete over total with a percentage.
- A rate line naming the window, and a forecast line giving weeks remaining and a projected date — or, when the window holds too few completions, the plain statement that it does, with no number.
- The existing derived-figures note extended to cover a derived forecast.
- Portfolio mode gains the rate only, staying one line per project.
- `path status --json` continues to be `metrics.build()`, which now carries all of it.

### Out of Scope

- Computing any of these figures. They arrive from `metrics` and `next`; this task must not reimplement them.
- The regenerated index, which is T-119, and the status page, which is T-120.
- Phase or narrative, which live in `AGENTS.md` and which this module has always declined to read or invent.

## Tasks

- [x] Rewrite `queue_lines` around readiness, keeping it a function of a row list so it tests with hand-built dicts.
- [x] Add the batches section, with an empty-batch-set case that prints nothing rather than an empty heading.
- [x] Add the backlog, rate, and forecast lines to `project_lines`.
- [x] Extend the derived-figures note to include the forecast.
- [x] Add the rate column to `render_portfolio`.
- [x] Extend `tests/test_status.py`.

## Acceptance Criteria

- [x] "Ready now" lists only tasks whose prerequisites are all complete, in the ranking order `path next` uses, capped with a count of the remainder.
- [x] "Waiting on prerequisites" is a separate section from "Blocked" and names what the listed tasks wait on.
- [x] Batches show derived status, tasks complete over total, and points complete over total.
- [x] The backlog line gives both task and point progress with a percentage.
- [x] The rate line names the window it covers.
- [x] With too few completions in the window, the forecast line states that plainly and prints no date.
- [x] A forecast resting on model-assigned effort or an inferred completion date is marked derived.
- [x] A project with no batches prints no batches section, and one with nothing ready prints no ready section, rather than empty headings.
- [x] Portfolio mode remains one line per project.
- [x] `path status` and `path next` never disagree about which task is first.

## Validation

- [x] A project whose lowest-identifier pending task is not startable is seen not to list it under "Ready now" — the defect the current output has.
- [x] A project with zero batches, zero ready tasks, and zero completions is seen to render without empty headings and without a spurious forecast.
- [x] The first entry under "Ready now" is asserted equal to `path next` output, so the two cannot drift.
- [x] A forecast built on an estimated effort is seen to carry the derived note.
- [x] Portfolio rendering is tested with projects of differing rates, including one with no completions at all.
- [x] `python3 -m unittest discover -s tests`, `ruff check scripts/ bin/path tests/`, and `./bin/path check` all pass.

## Notes

The test asserting that the first "Ready now" entry equals `path next` output is the one worth keeping forever. Two surfaces answering the same question from the same data will drift the moment one of them grows its own sorting, and a status board that disagrees with the command is worse than either alone.

Empty sections should vanish rather than print as headings with nothing under them. A glance should carry only what is true.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*
