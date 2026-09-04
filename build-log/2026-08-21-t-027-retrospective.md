---
type: Build Log Entry
title: T-027 Retrospective — indexes that cannot drift
description: ''
tags: []
timestamp: 2026-08-21T16:41:56Z
path:
  entry_type: RETROSPECTIVE
  related_tasks: [T-027]
  date: 2026-08-21
---

# T-027 Retrospective — indexes that cannot drift

## What was wrong

`tasks/index.md` and `build-log/index.md` were written once, at scaffold time,
and never again. `tasks.new_task` and `tasks.transition` — the two functions
that change what an index should say — did not touch them.

Three callers wrote indexes in three different shapes: `init_project` wrote a
single template entry, `refresh_project` healed a *missing* index with bare
filenames and no status, and `migrate` wrote the rich `status — title` form.
None of them owned keeping the result true.

## How it was found

Not by a test. In a sibling Path project the tasks index stopped at T-029 with 92
tasks on disk, listed T-018 as `pending` two weeks after it completed, and
carried a title the task had since been renamed away from. `path check` passed
against it — index files are OKF-reserved and frontmatter-free, so there is no
claim in them for `check` to validate. The build-log index there listed 56 of
142 entries.

An artefact nothing maintains and nothing validates will be wrong, and will
look authoritative while it is.

## What the fix is

Two functions in `okf.py`, next to `write_index`: `rebuild_tasks_index` and
`rebuild_build_log_index`. Both derive entries from frontmatter and rewrite
the whole file. Every mutation now calls them — `new_task`, `transition`, the
close path — and `refresh_project` rebuilds unconditionally rather than only
on absence, so `path .` repairs an index that exists and lies. `init_project`
and `migrate` were pointed at the same two functions, so one shape has one
owner.

Full rebuild rather than append, deliberately. An append-only index cannot
reflect a status change, cannot notice a deleted file, and cannot repair
itself — which is how these drifted. A rebuild makes the index a pure function
of its directory, and that is the only property that keeps it true.

## The regression this surfaced

Rebuilding the tasks index broke `test_unreferenced_deleted_id_may_be_reused`.
`next_id` scans every `.md` under `tasks/` for `T-NNN` references, and a
current index mentions every task — so deleting an unreferenced task no longer
freed its number.

The fix is to exclude OKF-reserved index files from the reference scan. An
index is derived from its directory, so every id it names already appears in a
file the scan reads; it can never be the sole surviving reference to anything.
Counting it made identifier allocation depend on a regenerated cache, which is
not a property anyone would have chosen on purpose. F-36 is unchanged in
behaviour.

## A note on what was not done

Index validation was deliberately left out of `path check`. A derived file
rebuilt on every mutation does not also need auditing: if the rebuild is
correct the check is redundant, and if it is wrong the check is the wrong
place to find out.
