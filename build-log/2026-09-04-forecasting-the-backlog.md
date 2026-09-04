---
type: Build Log Entry
title: 2026-09-04 — Forecasting the backlog, and grouping an index
description: Two positions reversed deliberately — measuring a rate, and grouping a reserved index.
tags: [metrics, forecasting, okf, conventions]
timestamp: 2026-09-04T00:00:00Z
path:
  date: 2026-09-04
  entry_type: DECISION
  related_tasks: [T-115, T-119]
---

# DECISION — Forecasting the backlog, and grouping an index

Two things shipped in B-003 contradict something Path had previously written down.
Both are deliberate. Recording them here rather than editing the old sentences into
agreement is the point: a system whose whole premise is that its documents stay true
cannot quietly revise its own history to match its present behaviour.

## Path now measures a rate. It said it would not.

[Architecture](../blueprints/01-architecture.md) said Path "is not a project
management tool. It measures effort and drift to improve its own process, not to
track velocity or team capacity." The [derived-metrics
entry](./2026-07-16-derived-metrics.md) said the same thing more bluntly: do not use
these figures to compare periods or estimate velocity.

`path status` now prints points per week over a trailing fourteen days and projects
the remaining backlog against it.

**What the original position got right, and keeps.** A velocity figure invites
comparison between people and between periods, and a tool that publishes the number
is partly responsible for what gets done with it. That concern was correct and is
untouched. There is no per-person breakdown, no per-agent breakdown, and no
period-over-period comparison. Path does not record who was fast, so there is
nothing to build one out of.

**What it got wrong.** The data was already there and already published. Completion
dates and effort points are in frontmatter, on the burn-up, and in
`path metrics --json`. Declining to divide two numbers Path had itself written down
did not prevent the inference; it moved the arithmetic into the reader's head, where
it arrived without a window, without provenance, and without any way to be wrong out
loud. "Are we going to finish this backlog" is a question the owner of a backlog is
entitled to ask, and Path was refusing to answer it while holding the answer.

**The narrowing that makes it safe.** The figure describes the backlog, never the
worker — F-57 says so as a requirement rather than as an intention. The window is
stated wherever the number appears, so nobody has to assume one. Below two
completions in the window, Path prints a refusal instead of a number and does not
widen the window to find data: a figure whose basis moved without saying so is worse
than no figure, because the reader believes they are looking at the recent rate. And
a projection resting on model-assigned effort or a git-inferred date is marked
derived, exactly as the burn-up already marks its points.

The [derived-metrics entry](./2026-07-16-derived-metrics.md) is left exactly as
written. It was true when it was written, and rewriting a record to agree with a
later decision is the specific dishonesty this build log exists to prevent.

## `tasks/index.md` now has headings. OKF calls it a directory listing.

[OKF Mapping](../blueprints/06-okf-mapping.md) records the specification's rule:
`index.md` is reserved, is a directory listing, and carries no frontmatter at all.
The regenerated index now groups its entries under `## Ready now`,
`## Waiting on prerequisites`, and so on.

**The reading taken.** Grouping a listing does not stop it being one. Every file in
`tasks/` appears exactly once, none is invented, none is omitted, and no frontmatter
claim is introduced — the three properties the reserved-name rule exists to protect.
What changed is the order and the headings, which is presentation.

**Why it was worth the judgment call.** The file is the one a person opens, and an
identifier-ordered list of statuses told them roughly what `ls` would. Path's whole
claim is that its documents are readable without its tooling; leaving "what can I
start" answerable only by a command would have made that claim false in the one
place it is easiest to test.

If a future OKF version is explicit that a reserved index must be flat, this is the
thing to change, and `okf.write_index` takes sections as an argument precisely so
that reverting is a one-line call site rather than a rewrite.

## What would reopen either of these

The forecast: any request for a per-person or per-period figure. That is the line the
original position drew, and it still holds — the answer is no, and this entry is why.

The index: an OKF revision that pins the structure of a reserved file.
