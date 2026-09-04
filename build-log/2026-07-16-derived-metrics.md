---
type: Build Log Entry
title: Backfilling metrics that were never recorded
description: Why migrated tasks carry estimated effort and inferred completion dates, and how they are marked.
tags: [decision, metrics, migration, okf]
timestamp: 2026-07-16T00:00:00Z
---

# DECISION — Backfilling metrics that were never recorded

## What we found

Building `path metrics` meant looking at what the existing projects actually contain. The answer was uncomfortable: almost none of the data the charts are supposed to plot has ever been recorded.

| Fact | lcm | lcg |
|------|-----|-----|
| Work orders | 45 | 23 |
| With an Effort Estimate | **0** | **0** |
| Complete, with no Completed date | 36 of 40 | 22 of 22 |
| With any change log entry | 0 | 0 |
| With any drift log entry | 0 | 2 |

The Effort Estimate convention, the Fibonacci scale, and the burn-up chart have all existed in the blueprints for some time and have been used exactly zero times. `backlog_total` computes to 0 for both projects, which means the burn-up chart on both status pages has always been empty. Nobody noticed, because an empty chart looks like a new project rather than a broken one.

Two smaller findings came out of the same look:

- Two lcm work orders record `**Status:** Complete` with a capital C. The old parser compared the string without normalising case, so those two were silently excluded from every metric. Migration lowercases status.
- The migration plan's stop-condition was "if burn-up totals shift, the migration lost data — stop." The baseline is 0. It would have compared 0 to 0 and passed no matter what the migration did to the files. The safety net for a 170-file migration was made of nothing. It has been replaced by per-task `path check` validation and a task-count and status-histogram comparison, which are things that actually exist.

## The decision

Kate chose to backfill both fields rather than leave them empty: effort estimated retrospectively by a model, completion dates inferred from git commit dates.

This was chosen against the recommendation in the plan, which was to leave both null and have `path check` require effort only before a task starts. The argument for leaving them null is that a fabricated metric is precisely what Path exists to prevent, and that an estimate assigned to already-finished work measures nothing except the estimator's hindsight. The argument for backfilling is that a burn-up covering only the last few weeks of a year-old project is not much of a burn-up, and that an approximate history is more useful than no history.

Both arguments are reasonable. It is the project owner's data and the project owner's call.

## What makes it safe enough

The risk of backfilling is not that the numbers are wrong — it is that in six months nobody will remember they were derived, and will read a chart of estimates as a record of measurements. So provenance is recorded in the data rather than in anyone's memory:

- `path.effort_source: estimated` — assigned retrospectively by a model
- `path.completed_source: inferred-git` — the commit date the file entered the repository

The absence of a source key means the value was recorded at the time, which is the only kind of number that is really evidence. `path metrics` counts derived values and publishes the count in its `provenance` block, and `status.html` renders a banner above the charts saying plainly that some of what follows is derived. A reader who cannot tell an estimate from a measurement will treat both as fact, so the page says which is which before it shows either.

## The known artifact

Most work order files have a single commit: they were added to the repository already marked complete. So the inferred completion date is the date the file was imported, not the date the work finished. For lcm this clusters roughly 40 tasks onto a handful of dates around 2026-06-05.

The burn-up will therefore show a near-vertical cliff at that point rather than a curve. **That shape is an artifact of the migration and means nothing about how the work actually proceeded.** It is documented here, in the provenance block, and on the page itself, because it will otherwise look like a period of superhuman productivity followed by a slowdown.

## Consequences

- Burn-up history before the migration is indicative, not evidence. Do not use it to compare periods, estimate velocity, or draw conclusions about pace.
- Metrics recorded after the migration are real, because `path new task` and `path task complete` capture them at the time.
- If the derived history later proves more misleading than useful, the fix is to drop the tasks carrying `effort_source: estimated` from the burn-up. The marker exists precisely so that remains possible.
