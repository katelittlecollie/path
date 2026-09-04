---
type: Build Log Entry
title: 2026-08-29 — Skip-Message Convention Added
description: ''
tags: [conventions, verification]
timestamp: 2026-08-29T00:00:00Z
path:
  date: 2026-08-29
  entry_type: CHANGE
  related_tasks: []
---

# 2026-08-29 — Skip-Message Convention Added

**Type:** CHANGE

## Summary

Added *Reporting a Check That Did Not Run* to
[Document Conventions](../blueprints/03-conventions.md): a check that is skipped,
disabled, or unable to reach what it needs must name the condition that caused it,
specifically enough to be falsified — and a blocker written into a task or a
session-close entry must name the measurement that actually established it.

## Why

A project using Path held a task blocked on a Stage-3 consistency measurement, on the
strength of a test skipping with `needs a reachable Ollama`. The message was read as a
fact about the machine and written into the task file and the session-close entry as
one. It was not. The test had asked a benchmark helper that hardcodes `localhost`
rather than the project's own configuration, which named a host on the LAN that was up
the whole time. The measurement took 67 seconds. The task closed the same session once
the skip was questioned.

Nothing was broken. The test was written the right way round — it skipped rather than
mocking a verdict it would then assert, which would have proved the parser and not the
prompt. What failed was the *record*: a skip is a single character in a row of dots, and
its message is the only thing distinguishing "we verified this" from "we did not". A
failing check demands attention on its own; a skipped one gets exactly as much scrutiny
as its message earns.

## Why it belongs in this document rather than in a project's own

Two reasons.

The first is that it is Document Freshness applied one layer down. That section already
says a document known to be inaccurate is worse than no document, and requires the
source of truth be corrected rather than annotated. A skip message is a document — often
the only one a reader sees about whether something was checked — and it had no rule.

The second is that the failure is not language- or framework-specific. It appears
identically in a test runner's skip, a CI gate that exits zero because its dependency
was absent, an accessibility audit that logged in as nobody, and a manual check recorded
in a task as done. Path is tool-agnostic; a convention that holds across all of those
belongs with the conventions, not in one project's blueprints where three other projects
would have to rediscover it.

## What this is not

It is not the general negative-control rule — that a check ship with proof it can fail.
This is the cheap corner of that family, and it is cheap precisely because a skip already
carries a message field whose entire job is to say why. Filling that field in is not a new
mechanism.

*Updated 2026-08-30:* the general rule was open when this was written; it is now settled,
as *A Check Must Be Seen to Fail* in the same document
(`build-log/2026-08-30-regression-test-must-fail-convention.md`). The two are one family at
two costs — this one names a condition in a field that already exists, that one buys a
deliberate extra run.
