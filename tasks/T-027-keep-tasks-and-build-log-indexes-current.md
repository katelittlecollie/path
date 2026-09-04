---
type: Task
title: Keep tasks and build-log indexes current
description: ''
tags: []
timestamp: 2026-08-21T16:41:59Z
path:
  id: T-027
  status: complete
  effort: 3
  created: 2026-08-21
  updated: 2026-08-21
  completed: 2026-08-21
  project: path
  drafted_by: Human
  completed_by: [Claude]
  requires: []
  implements: []
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-08-21T16:42:15Z
    result: pass
---

# Keep tasks and build-log indexes current

## Objective

`tasks/index.md` and `build-log/index.md` are written once, at scaffold time, and nothing ever updates them again. Every task created and every status transition after that moment makes them less true, silently. When this is done, both indexes will be derived artefacts with a single owner, rebuilt whenever their directory's contents change, and no longer capable of drifting from the frontmatter they describe.

## Context

`okf.write_index` is a general, correct, low-level writer. The defect is above it: three callers use it, at three different moments, in three different shapes, and none of them owns keeping the result current.

- `init.init_project` writes a tasks index containing exactly one entry: the template.
- `init.refresh_project` heals a **missing** index, with `(p.name, "")` — no status, no title. It fires only on absence, so an index that exists but is wrong is never touched.
- `migrate.migrate` writes the rich shape, `(name, f"{status} — {title}")`.

`tasks.new_task` and `tasks.transition` — the two functions that actually change what an index should say — do not touch it at all. So an index starts drifting with the first task after init and stays that way. `path check` does not catch it, because the index is OKF-reserved and frontmatter-free, so there is no claim in it for `check` to validate.

This was found in the wild. In a sibling Path project the tasks index stopped at T-029 with 92 tasks on disk, listed T-018 as `pending` when it had been complete for two weeks, and carried a title the task had since been renamed away from. `path check` passed against it. The build-log index there lists 56 of 142 entries.

The rich shape is the right one, and it is worth being explicit about why: an index whose entries are bare filenames tells a reader nothing a `ls` would not, whereas status and title make it a genuine table of contents that an agent can read instead of opening ninety files.

Relevant documentation:

- [Folder structure conventions](../blueprints/02-folder-structure.md)
- [Document conventions and status fields](../blueprints/03-conventions.md)

## Prerequisites

None.

## Scope

- Add one function that rebuilds `tasks/index.md` from task frontmatter, sorted by numeric task id, in the `status — title` shape.
- Add one function that rebuilds `build-log/index.md` from build-log frontmatter.
- Call them from every point that changes what the index should say: `tasks.new_task`, `tasks.transition`, and the close path that writes a build-log entry.
- Make `init.refresh_project` rebuild both indexes unconditionally rather than only when the file is missing, so `path .` repairs an existing stale index.
- Point `init.init_project` and `migrate.migrate` at the same functions, so one shape has one owner.
- Tests covering: creation, transition, close, the repair of an already-stale index, ordering, and a task whose frontmatter cannot be parsed.

### Out of Scope

- Adding index validation to `path check`. A derived file that is rebuilt on every mutation does not also need to be audited; if the rebuild is correct the check is redundant, and if it is wrong the check is the wrong place to find out.
- Any change to the OKF rule that index files carry no frontmatter.
- Indexes for `requirements/`, `blueprints/`, or `strategy/`, whose contents are near-static and hand-curated.

## Tasks

- [x] Add `rebuild_tasks_index(root)`, deriving entries from frontmatter and sorting by numeric id.
- [x] Add `rebuild_build_log_index(root)`.
- [x] Call the tasks rebuild from `new_task` and `transition`.
- [x] Call the build-log rebuild from the close path.
- [x] Make `refresh_project` rebuild both unconditionally.
- [x] Route `init_project` and `migrate` through the same two functions.
- [x] Handle a task file with malformed frontmatter without aborting the rebuild.
- [x] Tests for each call site, for ordering, and for stale-index repair.

## Acceptance Criteria

- [x] `path new task` leaves the new task present in `tasks/index.md`.
- [x] `path task complete T-NNN` leaves that task's index line reading `complete`.
- [x] `path close` leaves the new build-log entry present in `build-log/index.md`.
- [x] `path .` on a project whose tasks index is stale rewrites it to match the frontmatter on disk.
- [x] Entries are ordered by numeric task id, so T-009 precedes T-010.
- [x] A task file with unparseable frontmatter is skipped, the rest of the index still writes, and the skip is surfaced rather than swallowed.
- [x] Every index-writing path produces the same `status — title` shape.

## Validation

- [x] `python3 -m unittest discover -s tests` passes.
- [x] `ruff check scripts/ bin/path tests/` is clean.
- [x] `./bin/path check` passes.
- [x] Path's own `tasks/index.md` and `build-log/index.md` are correct after the change.

## Notes

Rebuilding the whole file rather than appending one line is deliberate. Appending is faster and is how the indexes came to be wrong: an append-only index cannot repair itself, cannot reflect a status change, and cannot notice a deleted file. A full rebuild from frontmatter is cheap at these sizes and makes the index a pure function of the directory, which is the only property that stops it drifting again.

The malformed-frontmatter case deserves care. Skipping silently would reintroduce exactly the failure mode this task exists to remove — an index that looks authoritative and is quietly incomplete.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*

*When complete, write a `RETROSPECTIVE` build log entry naming this task's id, and update `AGENTS.md`. `path check` verifies both.*
