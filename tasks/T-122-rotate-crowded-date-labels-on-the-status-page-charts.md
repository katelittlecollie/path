---
type: Task
title: Rotate crowded date labels on the status page charts
description: ''
tags: []
timestamp: 2026-09-04T18:42:11Z
path:
  id: T-122
  status: complete
  batch: null
  effort: 2
  created: 2026-09-04
  updated: 2026-09-04
  completed: 2026-09-04
  project: path
  drafted_by: claude-opus-5
  completed_by: [claude-opus-5]
  requires: []
  implements: [F-34]
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-09-04T18:42:52Z
    result: pass
---
# Rotate crowded date labels on the status page charts

## Objective

Make the dates under the status page charts readable. When this is done, no axis
label overlaps its neighbours at any realistic number of data points, and all
three date axes get their labels from one function rather than three copies of
the same three lines.

## Context

The burn-up plots one point per completed task, so the number of x-axis labels
grows with the project. Ten-character dates drawn horizontally and centred on
their ticks overlap each other from about six points onward, and by thirteen they
are unreadable — `2026-09-042026-09-04` runs together across the axis. The
volatility and drift charts draw dates the same way and will collide the same way
as soon as they have enough events.

This is presentation only. The figures are correct and arrive from the metrics
document; nothing about what is measured changes.

Relevant documentation:

- [F-34 — the status page is generated from the metrics document](../requirements/03-functional.md#metrics)
- [Metrics and the status page](../blueprints/03-conventions.md)

## Prerequisites

None.

## Scope

- A `dateLabel(x, y, text)` helper in the page's inline script, used by all three
  date axes.
- Labels rotated -45 degrees about their own tick with `text-anchor="end"`, so each
  label hangs down and to the left of the tick it belongs to.
- A deeper bottom padding on the three charts, since a rotated ten-character label
  is roughly 55px tall, and a chart height raised to keep the plot area from
  shrinking.

### Out of Scope

- Any change to what is measured, or to the metrics document.
- Thinning the labels — showing every nth date would hide data to solve a layout
  problem, and the rotation solves it without hiding anything.
- The decisions table, which has no axis.

## Tasks

- [x] Add `dateLabel` to the page script and use it from the burn-up, volatility, and drift charts.
- [x] Give the three charts a separate bottom padding and raise their height to match.
- [x] Regenerate `status.html` and confirm the labels no longer collide.

## Acceptance Criteria

- [x] No two axis labels overlap on any of the three charts at the current data volume.
- [x] Each label points at the tick it describes, so a reader can tell which point it belongs to.
- [x] The plot area is not visibly smaller than before despite the deeper label gutter.
- [x] All three date axes call one function; no chart carries its own copy of the label code.
- [x] Every figure on the page still comes from `metrics.build()`.

## Validation

- [x] The page is regenerated for this repository and opened at a normal window width, and the burn-up labels are read from the screenshot rather than assumed.
- [x] The rotated labels stay inside the chart's own vertical space and do not overlap the section below.
- [x] `python3 -m unittest discover -s tests`, `ruff check scripts/ bin/path tests/`, and `./bin/path check` all pass.

## Notes

The rotation direction is a choice worth stating, because both are defensible and
they read very differently. Labels rotated -45 degrees ascend to the right, and are
read by tilting the head to the left; anchoring at the end puts the tick at the top
right corner of the text, so the label appears to point at the data it describes.
The other direction would put the anchor at the start and have the text descend
away from its tick, which reads as if it belongs to the next point along.

The alternative fix — showing every nth label — was rejected. It solves a layout
problem by removing data, and on a burn-up the points are completions, so the
dropped labels are exactly the ones a reader is trying to date.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*
