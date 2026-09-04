---
type: Build Log Entry
title: 2026-09-04 — Sequence, batching, and forecasting — Retrospective
description: Eight tasks, one round of bookkeeping — and what that exposed.
tags: [batches, readiness, forecasting, status, okf]
timestamp: 2026-09-04T18:21:02Z
path:
  date: 2026-09-04
  entry_type: RETROSPECTIVE
  related_tasks: [T-114, T-115, T-116, T-117, T-118, T-119, T-120, T-121]
---

# Sequence, batching, and forecasting — Retrospective

Closes T-114, T-115, T-116, T-117, T-118, T-119, T-120, T-121.

## What Was Built

Path could always say what every task's status was and never what to do about it.
`path.requires` encoded a dependency graph that nothing traversed; `path.completed`
and `path.effort` encoded a rate that nothing derived. Both are now read.

A task is ready when it is pending and every prerequisite it names is complete.
`path next` returns the top-ranked one with enough detail to start cold — batch
first, then the task unblocking the most others, then lowest id. `path status` gained
that queue, a batches section, a backlog line, and a rate with a projection.
`tasks/index.md` is regenerated grouped by state, and `status.html` opens with a
forecast banner and a backlog board. A `Batch` document type groups tasks, and
`path batch start|complete`, `path check B-NNN`, and `path new retrospective --for`
let a batch pay one round of completion bookkeeping instead of one per member.

This entry is the demonstration: eight tasks, one retrospective.

## What Went Wrong

**The tasks were completed in the wrong order, once.** T-115 was marked complete
mid-session out of momentum, and `path check` immediately failed it for the two
things a complete task needs and it did not have — a retrospective and checked
boxes. It was reopened. The check did exactly its job; the slip was that the batch
workflow being built was not yet being used to run the work building it. The order
of operations for a batch is: finish every member, tick the boxes, `path batch
complete`, then one retrospective. Completing a single member early buys nothing and
breaks the run.

**Two modules wanted to import each other.** `tasks` and `batches` already formed a
cycle (batches reads tasks; tasks rebuilds an index that now needs batch progress),
and the grouped index in `okf` needed both. The first instinct was a deferred import
inside a function, which would have hidden the layering problem rather than fixing
it. What actually resolved it was noticing that the derivations `okf` needed —
readiness, ranking, batch status, rollups — are pure functions of a list of rows and
belong nowhere near file I/O. They moved to `next`, which imports nothing at all.
`batches` kept the files and the commands. The cycle disappeared because the layering
was wrong, not because Python needed persuading.

That move had a second payoff worth naming. Four surfaces now answer "what is next" —
`path next`, `path status`, `tasks/index.md`, `status.html` — and all four call the
same function. `tests/test_status.py` pins the first entry of the status queue to
what `path next` would name, because two surfaces answering one question will drift
the moment either grows its own sort.

**Fixtures that were wrong in an instructive way.** `tests/test_batches.py` first
built its projects with an `AGENTS.md` naming T-001, and every id assertion came out
one too high. That is `next_id` working correctly — a number referenced anywhere is
spoken for (F-36) — and the same rule surfaced twice more in this session: the real
tasks came out T-114 rather than T-031 because `check.py` cites the sibling project's T-113 in a
docstring, and the batch came out B-003 because the OKF mapping's own schema example
names B-002. All three are the rule doing its job, and all three were momentarily
read as bugs. The rule is right; it is just surprising every single time.

## What the Estimate Missed

Forty-nine points across eight tasks, and the split was roughly honest. The two that
diverged both diverged for the same reason: the work was not where the code was.

T-119 (5 points, "regroup the index") was the hardest task in the batch. Almost none
of that was the grouping. It was the import cycle above, and a conformance judgment —
OKF calls `index.md` a directory listing, and this gave it headings — that needed
deciding and recording rather than assuming. A task whose difficulty is a decision
rather than a diff will read small in its estimate every time.

T-121 (5 points, "documentation") was likewise not documentation. It was a reversal:
[architecture](../blueprints/01-architecture.md) said Path does not track velocity,
and T-115 made that false. Writing the amendment meant working out which half of the
original position survived — the refusal to measure people did; the refusal to divide
two numbers Path had already written down did not. That is in
[the decision](./2026-09-04-forecasting-the-backlog.md).

The lesson for the next estimate: a task that has to change a stated position is not
a documentation task, and pointing it as one under-reads it. The signal is in the
wording. "Update the blueprint" is 2 points. "The blueprint currently says the
opposite" is not.

## What Changed in the Documents

Requirements gained F-53 to F-59: batches and their membership rule, the grouped
index, the rate and its declared window, the prohibition on presenting it as
capacity, readiness and a next-work command, and batch-scoped operations. F-27's type
vocabulary gained `Batch`; F-41's enumeration gained the sequence-membership check.

Blueprints: [conventions](../blueprints/03-conventions.md) gained batch identifiers,
when to batch and when not to, and the rule that batch status is derived and never
stored; [OKF mapping](../blueprints/06-okf-mapping.md) gained the `Batch` schema,
`path.batch`, and `yq` invocations for the rate, readiness, and membership — each run
against this repository and matched to `path metrics --json`;
[architecture](../blueprints/01-architecture.md) was amended;
[the Definition of Done](../blueprints/05-definition-of-done.md) gained the new
mechanical items and its prose mirror of the checker's surface was updated.

One document was deliberately left alone. The
[derived-metrics entry](./2026-07-16-derived-metrics.md) says not to estimate velocity
from these figures. It was true when it was written, and editing a record to agree
with a later decision is the exact dishonesty a build log exists to prevent. The
decision entry supersedes it; it does not revise it.

## What This Exposed That Nothing Caught

Batch documents were briefly the only Path document exempt from validation. `check.run`
iterates `tasks/T-*.md`, then requirements, blueprints, build-log, and strategy — and
`tasks/B-*.md` fell in none of those, so a batch file would have passed by not being
looked at. It was found by writing the failing test first, which is the convention
working as intended rather than a near miss to be relieved about. The general shape is
worth remembering: a new document type is unvalidated by default, and the loop that
would have found it is the one nobody thinks to check.
