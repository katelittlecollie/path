---
type: Batch
title: Sequence, batching, and forecasting
description: Batches, readiness ranking, and backlog forecasting — the layer that tells Path's own users what to work on next.
tags: [batches, readiness, forecasting, status]
timestamp: 2026-09-04T18:01:16Z
path:
  id: B-003
  created: 2026-09-04
  updated: 2026-09-04
  project: path
  drafted_by: claude-opus-5
  sequence: [T-114, T-115, T-116, T-117, T-118, T-119, T-120, T-121]
---
# Sequence, batching, and forecasting

## Goal

Path records tasks faithfully and says nothing about sequence. When this batch is
done it answers three questions it currently cannot: what can I start, what is
grouped with what, and when does this backlog plausibly land — from `path status`,
from `path next`, from `tasks/index.md`, and from `status.html`, so the answer is
available whether or not anyone is at a terminal.

## Why These Together

They are one feature wearing eight task numbers. Readiness, batching, and the rate
all read the same frontmatter and all surface through the same three views; shipping
any one of them alone would leave a view half-answered and a blueprint half-true.

Two of the members exist only because of the others. T-121 amends an architecture
blueprint that currently says Path does not forecast, which becomes false the moment
T-115 lands — so the code and the correction cannot ship in different batches without
the repository contradicting itself in between. T-119 and T-120 are the same ranking
T-116 computes, rendered twice; separating them is how three surfaces start disagreeing.

The batch is also its own first test. It is the first batch this repository has ever
had, so every command being built here is exercised on the work that builds it, and
one round of completion bookkeeping covers all eight members rather than eight rounds
covering one each — which is the complaint that started this.

## Sequence

The execution order lives in `path.sequence`, maintained by `path batch add` and
`path batch order`.

The order is dependency order, and two constraints in it are not obvious. T-115 has
no prerequisite and could run first, but it is second because T-114 defines the
document type every later member reads. T-121 is last not for tidiness but because
documenting behaviour that has not settled produces a blueprint that needs amending
twice.

## Notes

The risk to watch is three surfaces answering one question differently. All of them
must read `metrics.build()` and none of them may sort or filter on its own; any
ordering rule that appears in a renderer rather than in the metrics document is a bug
in the making, and T-118 carries the test that pins the command and the status output
together.

---

*Membership lives on each task at `path.batch`; this file records only the order.
`path check` fails a batch whose sequence and membership disagree, so the two
cannot drift apart.*

*When the batch is complete, write one `RETROSPECTIVE` build log entry naming
every member in its `path.related_tasks` — `path new retrospective --for B-NNN`
fills that list in.*
