---
type: Build Log Entry
title: 2026-08-05 — Strategy Folder Added
description: ''
tags: []
timestamp: 2026-08-05T00:00:00Z
path:
  date: 2026-08-05
  entry_type: CHANGE
  related_tasks: []
---

# 2026-08-05 — Strategy Folder Added

**Type:** CHANGE

## Summary

Added `strategy/` as a first-class documentation folder, a sibling to
`build-log/`, for speculation, debate, and direction-setting — the thinking that
happens *before* anything is settled. Strategy discussions had been landing in
`build-log/`, where they were hard to find among the records of work actually
done, and where they blurred the log's meaning: a build-log entry reports what
happened, in the past tense, and a half-formed argument that reaches no
conclusion is not that.

## The Distinction

The line between the two folders is tense. `build-log/` records what was done,
decided, or changed. `strategy/` reasons about what might happen: options,
trade-offs, a direction worth trying. A strategy note is allowed to argue
several ways and settle nothing. When a strategy thread does resolve into a real
choice, the outcome is recorded where settled things live — a `DECISION`
build-log entry, `decisions-log.md`, or an updated requirement or blueprint —
not left in `strategy/`. This puts `strategy/` upstream of both the build log
and the decisions ledger.

## What Changed

- `strategy/index.md` created (OKF-reserved directory index).
- `blueprints/02-folder-structure.md`: `strategy/` added to the standard
  layout, given a naming convention (`[YYYY-MM-DD]-[topic].md`, same as
  build-log), and folded into the note on Path's own self-hosted structure.
- `blueprints/03-conventions.md`: new "Strategy Notes" section defining
  `type: Strategy Note` and the build-log/strategy line.
- `AGENTS.md`: navigation table row pointing at `strategy/`.
- `scripts/tasks.py`: `strategy/` added to the T-NNN reference scan, so a task
  id mentioned in a strategy note is protected from reuse.
- `scripts/check.py`: `strategy/` added to the OKF-conformance sweep, so
  strategy notes are validated for frontmatter, links, and secrets like any
  other document.

## What Deliberately Did Not Change

`strategy/` is opt-in, like `decisions-log.md`: it appears only once there is
something to put in it, so `init.py` does not scaffold it eagerly. It carries no
proof-of-done lifecycle — `check.py`'s rule that a completed task must have a
`build-log/` directory was left pointing at `build-log/` alone, because a
strategy note is speculation, not evidence that work was finished.
