---
type: Build Log Entry
title: T-026 Retrospective — the graphify invocation
description: ''
tags: []
timestamp: 2026-08-21T16:41:56Z
path:
  entry_type: RETROSPECTIVE
  related_tasks: [T-026]
  date: 2026-08-21
---

# T-026 Retrospective — the graphify invocation

## What was wrong

`scripts/graphify_run.py` called the graphify CLI with arguments it no longer
accepts:

```python
args = ["graphify", "--update"] if incremental else ["graphify"]
```

F-47 says initializing or refreshing a project must also build or update its
knowledge graph. It had not held for some time, on either arm.

## The two failure modes were not equally bad

`graphify --update` exits non-zero. The wrapper printed the error tail and
continued, exactly as F-50 requires. Loud, correct, recoverable.

Bare `graphify` prints its usage banner and exits **0**. `run()` read that as
success and reported "graphify: built the knowledge graph". Nothing was built.
This is the one worth remembering: a subprocess wrapper that trusts an exit
code alone will report success for any tool that answers an unrecognised
invocation with usage text. There is now a `_printed_usage` check and a test
pinning it, so the next CLI rename fails visibly instead of quietly.

## What the fix is

`graphify update <dir>` when a graph exists, `graphify extract <dir>` when one
does not, both verified against the installed CLI rather than against the help
text alone.

## The correction worth reading

The task originally claimed `graphify extract` degrades to AST-only when no
API key is set. That was generalised from a code-only sandbox directory. Run
against this repository — 34 docs — it exits non-zero with `no LLM API key
found`. Path shells out unattended, has no key to offer and nobody to ask, and
most Path projects are documentation, so the refusal is the common case rather
than an edge.

The cold-start arm now attempts the full build, and falls back to `graphify
update` (AST-only, no key needed) when it refuses, reporting the result as a
structure-only graph rather than pretending it is the full thing. `path .` on
this repository now produces 1,195 nodes where it previously produced nothing.

The general lesson is about method, not about graphify: the sandbox that
proved the fix was not shaped like the thing the fix runs on. Logged as drift
on the task for that reason.

## Requirements

F-47, F-48, F-50 unchanged. F-48's full-vs-incremental distinction is
preserved — a full build is still attempted first on a cold start; only its
failure is now survivable.
