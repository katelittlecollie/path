# Little Collie Path — AI Navigation Guide

Path is a file-based software development documentation system built by [Little Collie](https://littlecollie.com). It is also the first project to follow its own conventions: this repository is a Path project, self-hosted at the top level rather than nested under `.path/`.

## What Path Is

Path gives every project a structured, traceable set of documents — requirements, blueprints, tasks, and a build log — that an AI agent or a human can pick up and act on without prior context. Every document is an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) concept: Markdown with YAML frontmatter. Projects are independent and self-contained.

Path works with any AI tool, or none. Nothing it can do is available only through a tool-specific integration.

## How to Navigate This Project

| Need | Location |
|------|----------|
| What Path does and why | `requirements/01-overview.md` |
| Who uses Path and how | `requirements/02-user-stories.md` |
| Functional requirements | `requirements/03-functional.md` |
| Non-functional requirements | `requirements/04-non-functional.md` |
| System architecture | `blueprints/01-architecture.md` |
| Folder structure conventions | `blueprints/02-folder-structure.md` |
| Document conventions and status fields | `blueprints/03-conventions.md` |
| Definition of Ready (pre-execution checklist) | `blueprints/04-definition-of-ready.md` |
| Definition of Done (completion standards) | `blueprints/05-definition-of-done.md` |
| **OKF schema, and why Markdown not YAML** | `blueprints/06-okf-mapping.md` |
| **Global profile and precedence** | `blueprints/07-profile-and-precedence.md` |
| Task and batch templates | `tasks/TASK-TEMPLATE.md`, `tasks/BATCH-TEMPLATE.md` |
| Decision and build history | `build-log/` |
| Speculation, debate, and direction | `strategy/` |

## Available Commands

Path is a single command. Everything deterministic lives behind it — allocating
identifiers, shaping frontmatter, enforcing status transitions, validating,
reporting metrics — because none of that benefits from an executor's creativity
and all of it is quietly corrupted by improvisation.

```bash
path status                  # where the backlog stands, what is ready, what the batches are
path next [--batch]          # the next task to start, without reading every task file
path check [T-NNN|B-NNN]     # proof of done: validate a task, a batch, or the whole project
path metrics [--json]        # burn-up, rate and forecast, volatility, drift — read from frontmatter
path new task "<title>" --effort N [--batch B-NNN]
path new batch "<title>"
path new retrospective --for T-NNN|B-NNN
path task start|block|complete T-NNN
path batch add|remove|order|start|complete B-NNN [T-NNN ...]
path log change|drift|issue T-NNN "<note>"
path decision raise|resolve|list
path migrate [--apply]       # work orders -> OKF tasks (legacy projects)
path close                   # session-close entry, then regenerate status.html
```

`path next` exists so that choosing work costs one command rather than a read of
every task in the directory. A task is ready when it is pending and every task in
its `path.requires` is complete; that is computed once and shared by `path next`,
`path status`, `tasks/index.md`, and `status.html`, so none of them can answer the
question differently.

Judgment work is *not* behind the command. Writing an objective worth executing,
deciding scope, reviewing logged issues for the gap that let them through — that
lives in these documents, for a human or an AI to read and think about.

## Executing a Task

1. Read this file first for orientation.
2. Read the referenced task in `tasks/`.
3. Work through `blueprints/04-definition-of-ready.md` before beginning.
4. Follow the Context links in the task to read the relevant requirements and blueprints.
5. Complete every item in the task's task list.
6. Work through `blueprints/05-definition-of-done.md` before marking complete.
7. Write a `RETROSPECTIVE` build log entry, and update this file. The entry must declare the task in its `path.related_tasks` frontmatter — `path check` reads that field, not the prose, so a task named only in the body does not count (T-030). `path new retrospective --for T-NNN` fills that field in.
8. Run `path check T-NNN`. It verifies the completion claim mechanically, so the claim is checkable rather than trusted.

Working through a batch, the ceremony is paid once rather than per task: `path batch
start B-NNN`, then `path batch complete B-NNN`, then one `path new retrospective
--for B-NNN` naming every member, then `path check B-NNN`. Every rule still applies
to every member — it just applies once. See [when to batch](blueprints/03-conventions.md#when-to-batch-and-when-not-to).

## Working on Path Itself

Changes to Path's conventions go through Path's own task process (F-24, F-25). The tests are the contract:

```bash
python3 -m unittest discover -s tests    # 349 tests
ruff check scripts/ bin/path tests/
./bin/path check                          # Path must pass its own checks
```

`scripts/migrate.py` holds the only remaining parser for the legacy work order format and is meant to be deleted once every project has been migrated. Everything else reads frontmatter.

## Current Task

*(One line only — id, status, title. Details live in the task itself, not here. `path check` enforces this.)*

T-122 complete — Rotate crowded date labels on the status page charts.

## Project Status

*(Phase is one line. Do not append history here — that's what the build log is for.)*

**Phase:** Maintenance — batches, readiness ranking, and forecasting shipped (B-003); status page labels fixed (T-122); no task pending
**Last updated:** 2026-09-04

## Global Profile

If `$LCP_HOME` is set, read `$LCP_HOME/profile/index.md` (or run `path profile`) for the
project owner's working preferences. **Anything in this repository overrides it.**

Standing order: when you learn something true of the project owner, not this project —
a working preference, a stack default, a personal convention — persist it immediately
with `path profile add <doc> "<text>"` (`doc`: identity, working-style, conventions, or
stack). Never hand-edit the profile files.
