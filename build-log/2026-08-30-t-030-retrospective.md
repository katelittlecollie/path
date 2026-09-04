---
type: Build Log Entry
title: 2026-08-30 — T-030 The retrospective check was reading prose — Retrospective
description: ''
tags: [check, proof-of-done, okf, validation]
timestamp: 2026-08-30T00:00:00Z
path:
  date: 2026-08-30
  entry_type: RETROSPECTIVE
  related_tasks: [T-030]
---

# 2026-08-30 — T-030 The retrospective check was reading prose — Retrospective

**Type:** RETROSPECTIVE

## What this closed

`check_retrospective` searched every build-log entry for the literal strings
`"RETROSPECTIVE"` and the task id, anywhere in the file. Any entry that named a task in
passing satisfied the completion claim for it.

Found in use rather than in review. the sibling project's T-113 was marked complete and
`path check T-113` passed before a retrospective for it existed:
`2026-08-29-t-110-retrospective.md` names T-113 in its "what this does not cover" list.
A substring match cannot tell "this entry closes T-113" from "T-113 is explicitly out of
scope here" — the two sentences contain the same characters.

The check now reads `path.entry_type` and `path.related_tasks` from the entry's own
frontmatter.

## The decisions worth keeping

**The fields already existed.** `migrate.py` has written `entry_type` and `related_tasks`
into build-log frontmatter since the OKF migration, and all 96 of the sibling project's retrospectives
carry both. Nothing had to be invented or backfilled at scale; the check was reading the
wrong part of the document.

**Measured before changing.** A validator that starts failing on history is worse than a
loose one, so the impact was counted first: the sibling project 97 of 97 complete tasks still pass, path 2
of 4. The two failures are this repo's own T-026 and T-027 retrospectives, which have a
`path` block with `entry_type` and `date` but no `related_tasks`. Both are genuinely the
retrospective for their task; the field was never filled in. A tightening whose first act
is to find real sloppiness in its own repo is behaving correctly.

**Parse failures are someone else's finding.** `build-log/index.md` has no frontmatter by
design and a malformed entry is `check_document`'s business. Both are skipped here rather
than reported twice or allowed to crash the check — pinned by a test, because the old
implementation read raw text and could not have hit this.

**The failure message names the field.** "no RETROSPECTIVE build log entry lists T-030 in
its path.related_tasks" tells you the fix without reading the source. The previous
message said "mentions", which described the defect accurately and unhelpfully.

## What this cost elsewhere

Six test fixtures wrote build-log entries as bare `type: Build Log Entry` frontmatter with
the label in the body — the shape `migrate.py` produces *input* for, not output. They now
write the real schema, which makes them better fixtures regardless of this change.

F-41's wording said "referencing the task", which is what had been built. `AGENTS.md` step
7 and the same line in `init.py` — which stamps it into every new project — said "naming
the task id". All three now say what the check does.

## What is still open

**`related_tasks` means "related", not "closed by".** the sibling project's
`2026-08-29-t-110-retrospective.md` lists `[T-110, T-111, T-112, T-113]` while its body
says T-113 is out of scope there. Under this check that entry would still satisfy T-113's
claim if T-113 had no retrospective of its own — it does now, so nothing is currently
resting on it, but the overclaim is real and this change does not touch it.

Closing it properly means a field that means closure — `closes:` beside `related_tasks:` —
which is a schema change with migration consequences for every existing project. That is
its own task and its own thought, deliberately not a rider on this one.

## Process improvement

**A check that reads prose measures the document's vocabulary, not its claims.** This one
had two purpose-built frontmatter fields available and was grepping the body instead.
Worth a pass over the rest of `check.py` for the same shape: anywhere a fact is available
structurally and is being inferred from text instead.

**The proof-of-done stamp inherits the check's weaknesses silently.** `_record_proof`
writes `proof.checked_at` and `proof.result: pass` into the task's frontmatter whenever
the check exits clean. T-113 carries a passing stamp written against the loose rule. The
stamp records *that* a check passed, not *which version* of the check — so a tightening
leaves historical stamps looking identical to ones earned under the stricter rule. Worth
considering whether the stamp should carry a rule version, or whether that is more
bookkeeping than it earns.
