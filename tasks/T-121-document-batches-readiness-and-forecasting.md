---
type: Task
title: Document batches readiness and forecasting
description: ''
tags: []
timestamp: 2026-09-04T18:20:58Z
path:
  id: T-121
  status: complete
  effort: 5
  created: 2026-09-04
  updated: 2026-09-04
  completed: 2026-09-04
  project: path
  drafted_by: claude-opus-5
  completed_by: [claude-opus-5]
  requires: [T-114, T-115, T-116, T-117, T-118, T-119, T-120]
  implements: [F-25]
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-09-04T18:21:42Z
    result: pass
  batch: B-003
---
# Document batches, readiness, and forecasting

## Objective

Bring the documents level with the code. When this is done, the blueprints describe batches and derived batch status, the architecture blueprint no longer says Path does not forecast while Path forecasts, the Definition of Done lists the new mechanical checks, and the reasoning behind both judgment calls is recorded where a future reader will look for it.

## Context

Two of these are corrections to documents that would otherwise be false, not additions.

The architecture blueprint says Path "is not a project management tool… not to track velocity or team capacity", and the derived-metrics build log entry says not to use the figures to estimate velocity. T-115 adds a forecast. Leaving both standing would put the code in contradiction with a blueprint — the failure mode Path's own conventions call drift, and the one thing this repository cannot afford to model badly, since it is documented using itself.

The second is the OKF conformance judgment in T-119: `index.md` is specified as a directory listing, and the regenerated index now has section headings. The reading taken is that grouping a listing does not stop it being one. That belongs in a decision entry rather than in a commit message.

Relevant documentation:

- [F-25 — improvements to Path's conventions must reach its blueprints](../requirements/03-functional.md#path-as-a-project)
- [F-24 — Path is documented using Path](../requirements/03-functional.md#path-as-a-project)
- [Document conventions](../blueprints/03-conventions.md)
- [Definition of Done](../blueprints/05-definition-of-done.md)

## Prerequisites

Every other task in this group, so the documents describe what was actually built rather than what was planned. Recorded in `path.requires`.

## Scope

- `blueprints/03-conventions.md`: batch identifiers; when to batch and when not to; batch status is derived and never stored.
- `blueprints/06-okf-mapping.md`: the `Batch` schema, `path.batch` on tasks, and the `yq` invocations proving F-32 holds for readiness, batch rollups, and the rate.
- `blueprints/01-architecture.md`: amend the paragraph refusing project management so it permits backlog forecasting and still refuses capacity measurement.
- `blueprints/05-definition-of-done.md`: the new mechanical checks, tagged, and the prose mirror of the checker's surface updated.
- `AGENTS.md` and `README.md`: the new commands.
- A `DECISION` build log entry covering the forecasting reversal, its narrowing to the backlog, and the index conformance reading.
- A `RETROSPECTIVE` build log entry naming every task in this group in `path.related_tasks`, written with `path new retrospective`.

### Out of Scope

- Any code change. If documenting reveals a defect, it is logged as an issue against the task that owns it.
- The derived-metrics build log entry, which stays as written. It is a historical record of what was true when it was written, and rewriting it to match the present would be a lie about what happened.

## Tasks

- [x] Add batch conventions to `blueprints/03-conventions.md`.
- [x] Add the `Batch` schema and the `yq` invocations to `blueprints/06-okf-mapping.md`.
- [x] Amend the project-management paragraph in `blueprints/01-architecture.md`.
- [x] Update `blueprints/05-definition-of-done.md` with the new mechanical checks.
- [x] Update the command blocks in `AGENTS.md` and `README.md`.
- [x] Write the `DECISION` entry.
- [x] Write the `RETROSPECTIVE` with `path new retrospective`.

## Acceptance Criteria

- [x] No blueprint contradicts the shipped behaviour, and the architecture amendment states both what is now measured and what is still refused.
- [x] The `Batch` schema in the OKF mapping matches what the tooling actually writes, field for field.
- [x] Every documented `yq` invocation is run and produces the figure it claims.
- [x] The Definition of Done lists each new check with a tag, and its prose mirror of the checker's surface is accurate.
- [x] The command blocks in `AGENTS.md` and `README.md` list every new command.
- [x] The `DECISION` entry covers the forecasting reversal and the index conformance reading, and says why each was acceptable.
- [x] The `RETROSPECTIVE` names every task in this group in `path.related_tasks`.
- [x] `AGENTS.md` keeps its one-line Current Task and two-line Project Status.
- [x] The derived-metrics build log entry is unchanged.

## Validation

- [x] Each documented `yq` invocation is executed against this repository and its output compared to `path metrics --json`.
- [x] The `Batch` schema in the mapping is compared field by field against a batch the tooling generated.
- [x] `path check` is run and confirmed to pass, including the `AGENTS.md` line limits.
- [x] The architecture blueprint is reread against `metrics.forecast` to confirm no remaining contradiction.
- [x] `git diff` on the derived-metrics entry is confirmed empty.
- [x] `python3 -m unittest discover -s tests`, `ruff check scripts/ bin/path tests/`, and `./bin/path check` all pass.

## Notes

The temptation with the architecture blueprint is to quietly soften the sentence until it no longer conflicts. That is the wrong repair. The original position was reasoned and part of it still holds: measuring a person's pace is a thing Path should not do. What changed is the narrower claim that a backlog cannot be projected against its own recent rate. Say that the position changed, say which half survived, and leave the reasoning visible.

This repository is documented using itself, so a drifted document here is not a small internal inconsistency — it is the product failing its own first demonstration.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*
