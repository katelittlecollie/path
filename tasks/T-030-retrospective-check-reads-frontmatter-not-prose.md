---
type: Task
title: Retrospective check reads frontmatter, not prose
description: ''
tags: []
timestamp: 2026-08-30T17:03:37Z
path:
  id: T-030
  status: complete
  effort: 2
  created: 2026-08-30
  updated: 2026-08-30
  completed: 2026-08-30
  project: path
  drafted_by: Claude Opus 5
  completed_by: []
  requires: []
  implements: [F-41]
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-08-30T17:03:53Z
    result: pass
---

# Retrospective check reads frontmatter, not prose

## Objective

`check_retrospective` scanned every build-log entry for the literal strings
`"RETROSPECTIVE"` and the task id, anywhere in the file. Any entry that happened to name
a task in passing satisfied the completion claim for it. When this is done, the check
reads the fields built for the purpose — `path.entry_type` and `path.related_tasks` — so
an entry has to *declare* the task it closes rather than merely mention it.

## Context

Found in use, not in review. the sibling project's T-113 was marked complete and `path check T-113`
passed before any retrospective for it had been written: `2026-08-29-t-110-retrospective.md`
names T-113 in its "what this does not cover" list, and a substring match cannot tell the
difference between "this entry closes T-113" and "T-113 is explicitly out of scope here".

The fields were already there and already populated — `migrate.py` has written
`entry_type` and `related_tasks` into build-log frontmatter since the OKF migration, and
every one of the sibling project's 96 retrospective entries carries both. The check was simply reading
the prose instead.

Measured before changing anything, because a validator that starts failing on history is
worse than a loose one:

| project | complete tasks | pass on prose match | pass on `related_tasks` |
|---|---|---|---|
| sibling | 97 | 97 | 97 |
| path | 4 | 4 | 2 |

The two path failures are this repo's own: `2026-08-21-t-026-retrospective.md` and its
T-027 sibling have a `path` block with `entry_type` and `date` but no `related_tasks`.
Both are genuinely the retrospective for their task — the field was just never filled in.
That is the check finding real sloppiness in its own repo on the first run, which is the
outcome you want from a tightening.

Relevant documentation:

- [F-41 — proof of done validation](../requirements/03-functional.md)

## Prerequisites

None.

## Scope

**Read `path.entry_type` and `path.related_tasks`.** An entry satisfies a completion claim
when its `entry_type` is `RETROSPECTIVE` and the task id appears in its `related_tasks`
list. Nothing about the body text counts any more.

**Skip what will not parse.** `build-log/index.md` has no frontmatter by design, and a
malformed entry is `check_document`'s finding to report. Neither is this check's business
and neither may make it crash.

**Say what to do in the failure message.** "no RETROSPECTIVE build log entry lists T-030
in its path.related_tasks" names the field, so the fix is obvious without reading the
source.

**Update F-41 to match.** The requirement said "referencing the task", which is what was
built. It now says what the check actually does.

**Fill in this repo's two unstamped entries**, which the tightening exposes.

### Out of Scope

- Distinguishing "closes" from "relates to". `related_tasks` is a relatedness field and is
  being read as a closure claim, which is a slight stretch — see Notes.
- Any change to how `migrate.py` derives the two fields.
- Backfilling `related_tasks` in other projects; the sibling project needs none.

## Tasks

- [x] Rewrite `check_retrospective` to read frontmatter — `path.entry_type` and `path.related_tasks`
- [x] Handle unparseable and frontmatter-less entries without failing — `okf.OKFError` is skipped, not reported
- [x] Update F-41 to describe the tightened check — and `AGENTS.md` step 7 and the same line in `init.py`, which stamps it into every new project
- [x] Add `related_tasks` to this repo's T-026 and T-027 retrospectives
- [x] Cover the name-drop case, the wrong-entry-type case, and the unparseable case with tests — `TestRetrospective`, six cases

## Acceptance Criteria

- [x] A retrospective listing the task in `related_tasks` satisfies the check
- [x] An entry that names the task only in its prose does not — `test_a_name_drop_in_the_prose_does_not_count`, built from the T-113 case that prompted this
- [x] A non-RETROSPECTIVE entry listing the task in `related_tasks` does not
- [x] `build-log/index.md` does not break the check
- [x] The failure message names `path.related_tasks`
- [x] Both repos pass `path check` afterwards, with no task newly failing in the sibling project — all 97 complete sibling-project tasks still pass

## Validation

- [x] Unit: retrospective with the task in `related_tasks` passes
- [x] Unit: retrospective listing several tasks, one of them this one, passes
- [x] Unit: retrospective for a different task fails
- [x] Unit: task named in the prose but not in `related_tasks` fails
- [x] Unit: `entry_type: DECISION` listing the task fails
- [x] Unit: a frontmatter-less `index.md` alongside a valid retrospective still passes
- [x] Integration: `path check` clean in the path repo and in the sibling project, all 97 complete sibling-project tasks still passing. 353 tests pass, ruff clean.

## Notes

**The residual, and why it is left.** `related_tasks` means "related", not "closed by".
the sibling project's `2026-08-29-t-110-retrospective.md` lists `[T-110, T-111, T-112, T-113]` while its
body says T-113 is out of scope there — so under this check that entry would still satisfy
T-113's claim if T-113 had no retrospective of its own. The tightening removes the
accidental pass (prose mentions) but not the over-broad declaration. Closing that properly
means a field that means closure — `closes:` beside `related_tasks:` — which is a schema
change worth its own task and its own thought, not a rider on this one.

The general shape is worth remembering: a check that reads prose is measuring the
document's vocabulary, not its claims. Every field this validator needs was already in the
frontmatter.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*

*When complete, write a `RETROSPECTIVE` build log entry naming this task's id, and update `AGENTS.md`. `path check` verifies both.*
