---
type: Task
title: Fix the graphify invocation in graphify_run
description: ''
tags: []
timestamp: 2026-08-21T16:41:59Z
path:
  id: T-026
  status: complete
  effort: 2
  created: 2026-08-21
  updated: 2026-08-21
  completed: 2026-08-21
  project: path
  drafted_by: Human
  completed_by: [Claude]
  requires: []
  implements: []
  change_log: []
  drift_log:
  - date: 2026-08-21
    kind: correction
    effort_to_correct: 1
    note: 'graphify extract hard-errors on a doc-heavy corpus when no LLM API key is set; it degrades to AST-only only for a code-only corpus. Verified against the real CLI on the Path repo itself. Since Path runs unattended and most Path projects are doc-heavy, the cold-start arm now falls back to ''graphify update'' (AST-only, no key) when the full build refuses. F-48''s full-vs-incremental distinction is preserved: a full build is still attempted first.'
  issues: []
  proof:
    checked_at: 2026-08-21T16:42:14Z
    result: pass
---

# Fix the graphify invocation in graphify_run

## Objective

`scripts/graphify_run.py` invokes the graphify CLI with arguments that command no longer accepts, so F-47 has not actually held for some time: `path .` never builds or updates a knowledge graph. When this is done, both arms of the invocation will name real graphify subcommands, verified against the installed CLI, and F-48's incremental-vs-full distinction will be a real distinction rather than two spellings of a no-op.

## Context

The module chooses between two argument lists:

```python
args = ["graphify", "--update"] if incremental else ["graphify"]
```

Both are wrong against the current graphify CLI, and they fail in different ways:

- `graphify --update` exits non-zero with `error: unknown command '--update'`. This arm at least fails loudly — the caller prints the error tail and continues, per F-50.
- Bare `graphify` prints its usage banner and **exits 0**. This arm is the more damaging one: `run()` reads the zero exit as success and reports "graphify: built the knowledge graph", when nothing was built. A silent false success is worse than the loud failure, because nothing downstream has any reason to doubt it.

The correct subcommands, confirmed against `graphify --help` and by running each one:

- `graphify update <path>` — re-extracts code files and updates an existing graph. No LLM, no API key.
- `graphify extract <path>` — headless full extraction. Its semantic half needs an LLM backend. With no API key it degrades to AST-only **only for a code-only corpus**; the moment the corpus holds a doc, paper, or image it exits non-zero with `no LLM API key found`. That matters here: Path shells out unattended, has no key to offer and no one to ask, and most Path projects are documentation — so the refusal is the common case, not the edge. The cold-start arm therefore falls back to `graphify update`, which needs no key and still writes `graph.json`.

Relevant documentation:

- [F-47, F-48, F-50](../requirements/03-functional.md)

## Prerequisites

The graphify CLI must be installed to verify the fix by hand. The tests themselves inject every subprocess call and never invoke it.

## Scope

- Correct both argument lists in `scripts/graphify_run.py` to name real subcommands, passing the project directory explicitly.
- Update `tests/test_graphify_run.py`, which currently asserts the broken argv and so locks the bug in as the contract.
- Add a regression test for the silent-success arm: a zero exit whose output is graphify's usage banner must not be reported as a successful build.

### Out of Scope

- Any change to `scripts/graphify_check.py`. Presence and version checking is a separate concern and is not broken.
- Semantic (LLM) extraction from `path .`. The cold-start arm degrades to AST-only by design, because Path runs unattended and has no key to offer. Richer extraction stays a deliberate act the user performs by running graphify directly.
- Pinning a graphify version floor, or any general guard against future CLI drift.

## Tasks

- [x] Replace the incremental argv with `graphify update <project_dir>`.
- [x] Replace the full-build argv with `graphify extract <project_dir>`.
- [x] Fall back to `graphify update <project_dir>` when the full build refuses for want of an API key, and say the resulting graph is structure-only.
- [x] Detect the usage-banner-on-exit-0 case and treat it as failure rather than success.
- [x] Update the two tests asserting the old argv.
- [x] Add a test that a zero exit printing the usage banner returns False.
- [x] Verify both subcommands by hand against the installed graphify CLI.

## Acceptance Criteria

- [x] With no existing graph, `run()` invokes `["graphify", "extract", "<project_dir>"]`.
- [x] When that full build fails, `run()` retries with `update`, returns True, and reports the graph as structure-only.
- [x] A first attempt that fails but is rescued by the fallback is not reported as an error.
- [x] The incremental arm never falls back — a failure there is a real failure.
- [x] With an existing `graphify-out/graph.json`, `run()` invokes `["graphify", "update", "<project_dir>"]`.
- [x] A zero-exit run whose stdout is graphify's usage banner returns False and does not claim a graph was built.
- [x] Every existing F-50 guarantee still holds: missing binary, timeout, OSError, and non-zero exit each return False without raising.
- [x] `path .` on a project with an existing graph updates that graph, confirmed by an advanced `graph.json` mtime.

## Validation

- [x] `python3 -m unittest discover -s tests` passes.
- [x] `ruff check scripts/ bin/path tests/` is clean.
- [x] `./bin/path check` passes.
- [x] Both subcommands are run by hand against the real CLI on a throwaway directory, confirming exit 0 and a written `graph.json`.

## Notes

The silent-success arm is the reason this task exists as more than a two-string edit. The lesson generalises past graphify: a subprocess wrapper that trusts an exit code alone will report success for any tool that answers an unrecognised invocation with a usage message. The new test pins that behaviour so a future CLI rename fails loudly instead of quietly.

`graphify extract` prints a "next: run `graphify cluster-only`" hint and does not itself write `GRAPH_REPORT.md`; `graphify update` writes the report and `graph.html` as well. So the fallback path produces *more* than the full-build path does, minus the semantic layer. Neither matches what a direct `/graphify` run produces, and it is worth knowing that before anyone treats the three as equivalent.

The initial version of this task asserted that `graphify extract` degrades to AST-only without a key. That was generalised from a code-only sandbox and is wrong for the doc-heavy corpus every Path project actually is — caught only by running the change against this repository. It is logged as drift rather than quietly corrected, because the lesson is about where the test was run, not about the CLI.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*

*When complete, write a `RETROSPECTIVE` build log entry naming this task's id, and update `AGENTS.md`. `path check` verifies both.*
