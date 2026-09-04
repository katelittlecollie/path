---
type: Build Log Entry
title: 2026-09-04 — Rotate crowded date labels on the status page charts — Retrospective
description: Axis labels rotated so the burn-up's dates stop colliding.
tags: [status-page, charts, presentation]
timestamp: 2026-09-04T18:42:12Z
path:
  date: 2026-09-04
  entry_type: RETROSPECTIVE
  related_tasks: [T-122]
---

# Rotate crowded date labels on the status page charts — Retrospective

Closes T-122.

## What Was Built

The three date axes on `status.html` — burn-up, requirements volatility, AI workflow
drift — now draw their labels through one `dateLabel` helper, rotated -45 degrees
about their own tick and anchored at the end, so each label hangs down and to the
left of the point it describes. The charts gained a separate, deeper bottom padding
for the rotated text and a matching height increase, so the plot area did not shrink
to pay for the gutter.

## What Went Wrong

Nothing in the change itself. Two things about how it was found are worth recording.

**The defect was only visible in a screenshot.** Every gate passed, both before and
after — 503 tests, ruff, `path check` — and none of them could have caught this,
because none of them looks at the page. The burn-up has drawn colliding labels for
as long as it has had more than a handful of points, and it was reported by a human
looking at it. That is the honest limit of the mechanical half of the Definition of
Done: it verifies that a claim is true, not that a rendering is legible.

**It was reported the day after the page was rewritten.** B-003 added a banner and a
board to this file and its retrospective claimed the page had been "generated and
opened". It had been — the screenshot from that check is in the session — and the
colliding axis underneath went unremarked, because the check was scoped to the new
sections rather than to the page. Opening a page to verify a change is not the same
as looking at the page.

## What the Estimate Missed

Two points, and two points was right. The rotation itself is one attribute; the
padding is arithmetic. The only decision that took any thought was the rotation
direction, and it is recorded in the task's Notes rather than left to be re-derived:
labels ascending to the right put the tick at the corner of the text, so a label
appears to point at its own data. The other direction reads as if each label belongs
to the next point along.

The rejected alternative is worth keeping too. Thinning to every nth label would have
fixed the collision by removing data, and on a burn-up every point is a completion —
the dropped dates are exactly the ones a reader is trying to read.

## What Changed in the Documents

Nothing. This changed how a generated page draws text and touched no convention, no
requirement, and no schema. `scripts/path_status_page.py` carries the reasoning in
comments at the helper, which is where someone changing the layout will be looking.

The one thing worth carrying forward is a gap rather than a change: no gate on this
project looks at rendered output, so visual defects reach a person by reaching a
person. Worth a `[Judgment]` line in the Definition of Done if it happens again —
but once is an anecdote, and adding a checklist item on the strength of one report is
how checklists stop being read.
