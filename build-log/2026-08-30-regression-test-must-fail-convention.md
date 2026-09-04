---
type: Build Log Entry
title: 2026-08-30 — Negative-Control Convention Added — A Check Must Be Seen to Fail
description: ''
tags: [conventions, verification, testing]
timestamp: 2026-08-30T00:00:00Z
path:
  date: 2026-08-30
  entry_type: CHANGE
  related_tasks: []
---

# 2026-08-30 — Negative-Control Convention Added — A Check Must Be Seen to Fail

**Type:** CHANGE

## Summary

Added *A Check Must Be Seen to Fail* to
[Document Conventions](../blueprints/03-conventions.md), directly after
*Reporting a Check That Did Not Run*: a check a task adds or repairs must be observed
failing, for the reason it exists to catch, before the task is complete.

Two shapes, one rule. A **guard** — a test assertion, a lint or accessibility gate, a CI
job, a validator — owes a negative control, run once, proving it can fail. A **test
pinning a diagnosed defect** owes a run against the unmodified code, proving it fails
there. Four rules follow: make it fail on purpose once; check the failure *reason* rather
than just the failure; keep the negative case permanently where it can be kept; and where
it genuinely cannot be done, say so in the build log rather than silently.

## Why

This closes a question that had been open in a project using Path since 2026-08-21, raised
after a fourth defect of one shape and resolved by its owner on 2026-08-30 after a fifth.
The shape: **a guard whose failure mode is a pass.** All five, and in every one the
guardrail existed, was pointed at the right thing on paper, and was itself unfalsifiable:

1. An a11y/HTML gate whose login step never logged in — it audited the login page nineteen
   times per theme and reported clean.
2. A launcher failure masked behind that same gate.
3. An HTML validator that exited 0 without a JRE ever starting.
4. A test asserting "an un-bannable card carries no ban hook", which passed against the
   page's shortcut script rather than the card markup, because its helper sliced to
   end-of-document.
5. A regression test for a database lock error that passed against completely unhardened
   code, because the driver's default timeout already absorbed the case it reproduced.

The fifth is the one that made the cost concrete, because it was a near-miss rather than a
post-hoc discovery. The incident report it came from named a cause — no busy timeout was
configured — with the specific confidence of something verified. Both halves were wrong:
the driver passes a five-second timeout by default, and in the journal mode actually in use
that handler is bypassed entirely for the conflict that occurred. The plausible fix
followed directly from the stated cause, would have passed a test written against it, and
would have closed the task green with the defect untouched. What caught it was running the
reproduction against the *unhardened* code and finding it passed. Sixty seconds.

Note what did not catch it: the full suite passed, lint passed, `path check` passed, and
every Definition of Done item was satisfiable. Every existing gate was green against a test
that pinned nothing.

## The two sub-questions, and how they were answered

**SCOPE** — the open question was whether the rule covers every negative assertion, only
CI gates and guards, or some named middle. Answered: **the named middle.** A check a task
*adds or repairs*, plus tests pinning a *diagnosed* defect.

"Every negative assertion" was rejected as correct in principle and unaffordable in
practice — and a rule nobody can follow gets skipped everywhere, including where it
mattered. "CI gates only" was rejected because it excludes two of the five instances,
including the one that prompted the resolution.

The line drawn is **ownership and intent, not test type**: if a task's point is that
something is now caught, that catching is the deliverable and needs the same proof as any
other deliverable. An assertion written in passing, as ordinary coverage, does not.

**FORM** — DoD checklist item, convention, or something mechanical. Answered:
**convention.** The originating project's DoD judgment list is already sixteen items long,
and the decision text itself observed that a seventeenth skimmed at close time is weaker
than a sentence read at the moment the check is written. A mechanical option — a required
mutation check on new gate scripts — was considered and not adopted: it is buildable but
would only reach one of the five shapes, and none of the four non-gate instances.

## Why it belongs in this document rather than in a project's own

Same two reasons as the skip-message convention it sits beside.

It is framework- and language-agnostic: a first-run pass carries no information in any test
runner, in any language, for any kind of check. And it is a rule read when *writing* a
check, which is where a convention lands and where a Definition of Done item does not.

The originating project's retrospective first recommended this land in its own
`blueprints/03-conventions.md` without noticing that the file it named is Path's. That
project deliberately has no local conventions file — a second copy is the thing its
`CLAUDE.md` exists to refuse — which is the same call recorded on 2026-08-29 for the
skip-message convention.

## Relationship to the skip-message convention

They are one family at two costs, and the earlier entry said this one was still open. It no
longer is:

- **Cheapest** — *Reporting a Check That Did Not Run* (2026-08-29). A skip names its
  condition. No new mechanism; a skip already has a message field whose job is to say why.
- **This** — a check is seen to fail. One deliberate extra run, at the moment the check is
  written, and it buys the thing that run is uniquely able to tell you: whether the check
  checks.
