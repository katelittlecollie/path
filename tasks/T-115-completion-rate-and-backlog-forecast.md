---
type: Task
title: Completion rate and backlog forecast
description: ''
tags: []
timestamp: 2026-09-04T18:20:58Z
path:
  id: T-115
  status: complete
  effort: 5
  created: 2026-09-04
  updated: 2026-09-04
  completed: 2026-09-04
  project: path
  drafted_by: claude-opus-5
  completed_by: [claude-opus-5]
  requires: []
  implements: [F-56, F-57]
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-09-04T18:21:42Z
    result: pass
  batch: B-003
---
# Completion rate and backlog forecast

## Objective

Derive a completion rate from the dates and effort Path already records, and project the remaining backlog against it. When this is done, `metrics.build()` carries a rate and a forecast alongside the burn-up, both stating the window they rest on and both refusing to produce a number when the evidence is too thin to support one.

## Context

`path.completed` and `path.effort` already encode everything a rate needs, and nothing reads them for that purpose. `metrics.burnup` walks exactly this data to plot cumulative points and stops there.

This task reverses a stated position, and does so deliberately rather than quietly. [Architecture](../blueprints/01-architecture.md) says Path "is not a project management tool… not to track velocity or team capacity", and the derived-metrics build log entry says not to use the figures to estimate velocity. The narrowing that keeps the original concern intact is that the forecast describes *this backlog's remaining points* and never a person's or a team's capacity — which is what F-57 now says. Amending the blueprint and recording why belongs to T-121; this task must not leave code contradicting a blueprint that still says the opposite, so the two land together in the same batch.

Relevant documentation:

- [F-56, F-57 — rate and forecast](../requirements/03-functional.md#metrics)
- [F-32 — every metric derivable from frontmatter alone](../requirements/03-functional.md#metrics)
- [Architecture — what Path measures and why](../blueprints/01-architecture.md)
- [Metrics from frontmatter](../blueprints/06-okf-mapping.md#metrics-from-frontmatter)

## Prerequisites

None.

## Scope

- `velocity(rows, window_days=14)` in `scripts/metrics.py`: points and tasks completed within the trailing window, expressed as points per week, carrying the window bounds and a derived flag.
- `forecast(rows, window_days=14)`: remaining points over the rate, yielding weeks remaining and a projected finish date, with a `sufficient` flag.
- Both added to `metrics.build()`, and the rate added to `metrics.portfolio()`.
- The insufficiency rule: fewer than two completions inside the window yields `sufficient: false` and no projected date. The window is never widened silently.
- The provenance rule: when any contributing task carries `effort_source: estimated` or `completed_source: inferred-git`, the result is flagged derived, matching how `burnup` already marks its points.
- Remaining backlog counts non-complete tasks only, and reports how many of them carry no effort estimate.
- The `yq` invocations proving F-32 holds for the rate, documented in the OKF mapping.

### Out of Scope

- Printing any of it. `path status` is T-118 and the status page is T-120.
- Amending the architecture blueprint and writing the decision entry. That is T-121.
- Any per-person, per-agent, or per-period comparison. F-57 forbids it and no code here should make it easy.

## Tasks

- [x] Add `velocity` to `scripts/metrics.py`, taking a row list so it tests with hand-built dicts.
- [x] Add `forecast` to `scripts/metrics.py`, including the insufficiency and provenance rules.
- [x] Extend `metrics.build()` with both, and `metrics.portfolio()` with the rate.
- [x] Document the equivalent `yq` invocations in `blueprints/06-okf-mapping.md`.
- [x] Extend `tests/test_metrics.py` with the rate and forecast cases.

## Acceptance Criteria

- [x] `velocity` counts only tasks whose `path.completed` falls inside the trailing window, and expresses the result as points per week regardless of window length.
- [x] `forecast` divides remaining non-complete points by that rate and returns weeks remaining and a projected date.
- [x] With fewer than two completions in the window, `sufficient` is false, no projected date is returned, and the window is unchanged.
- [x] A contributing task carrying `effort_source: estimated` or `completed_source: inferred-git` flags the result derived.
- [x] The window length is present in the returned structure, so any caller can state it.
- [x] `path metrics --json` carries both, and every figure in them is reproducible with a documented `yq` invocation over the same files.
- [x] Tasks with no effort estimate are counted and reported rather than treated as zero.

## Validation

- [x] Zero completions in the window is seen to yield `sufficient: false` rather than a division by zero.
- [x] Exactly one completion in the window is seen to yield `sufficient: false`, since one point establishes no rate.
- [x] A completion one day outside the window is seen to be excluded, and one day inside included.
- [x] A task with `effort_source: estimated` inside the window is seen to flag the forecast derived.
- [x] A backlog containing an unestimated task is seen to report that count rather than silently under-forecasting.
- [x] The documented `yq` invocation is run against this repository and its answer matched against `path metrics --json`.
- [x] `python3 -m unittest discover -s tests`, `ruff check scripts/ bin/path tests/`, and `./bin/path check` all pass.

## Notes

The insufficiency rule is the important one and it is easy to get wrong in a way nobody notices. The tempting behaviour when a two-week window is empty is to widen it until it holds something. That produces a number whose basis moved without saying so, which is worse than no number at all — the reader believes they are looking at the recent rate. Say the window is empty and stop.

Fourteen days is the default because it is short enough to reflect the current rate and long enough to survive a quiet week. It stays a parameter so a caller can ask for something else, and whatever is used is stated wherever the figure is shown.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*
