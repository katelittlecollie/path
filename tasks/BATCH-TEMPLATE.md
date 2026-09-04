---
# Every value here is filled in by `path new batch`. Square-bracket placeholders
# are fine in the body below, but not up here: `[like this]` is a YAML flow
# sequence, not a blank to fill in, and a `?` inside one is a parse error.
#
# There is deliberately no `status` and no `completed`. Both are derived from
# the batch's members at read time, for the same reason a decision's age is
# never stored: a computed value written to disk is a second copy, and a second
# copy is a thing that drifts.
type: Batch
title:
description:
tags: []
timestamp:
path:
  id:
  created:
  updated:
  project:
  drafted_by:
  sequence: []
---

# [Short Descriptive Title]

## Goal

[One paragraph. What is true when this whole batch is done that is not true now? A batch earns its existence by having an outcome its members do not have separately.]

## Why These Together

[Why this is one sitting's work rather than several. Shared context, a shared surface, a shared round of bookkeeping — say which. If the honest answer is "they were next to each other in the list", they are not a batch.]

## Sequence

The execution order lives in `path.sequence`, maintained by `path batch add` and
`path batch order`. Note here only what the order depends on that the ordering
itself cannot say.

## Notes

[Known risks, edge cases, anything the executor should carry across all members.]

---

*Membership lives on each task at `path.batch`; this file records only the order.
`path check` fails a batch whose sequence and membership disagree, so the two
cannot drift apart.*

*When the batch is complete, write one `RETROSPECTIVE` build log entry naming
every member in its `path.related_tasks` — `path new retrospective --for B-NNN`
fills that list in.*
