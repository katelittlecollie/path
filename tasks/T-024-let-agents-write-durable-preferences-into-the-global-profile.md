---
type: Task
title: Let agents write durable preferences into the global profile
description: ''
tags: []
timestamp: 2026-07-19T17:33:23Z
path:
  id: T-024
  status: complete
  effort: 8
  created: 2026-07-19
  updated: 2026-07-19
  completed: 2026-07-19
  project: code
  drafted_by: Claude Sonnet 5
  completed_by: [Claude Sonnet 5]
  requires: []
  implements: [F-51, F-52]
  change_log: []
  drift_log: []
  issues: []
  proof:
    checked_at: 2026-07-19T17:33:26Z
    result: pass
---

# Let agents write durable preferences into the global profile

## Objective

Today the profile at `$LCP_HOME/profile/` is read-only from an agent's side: `path profile` prints it, `path install-shims` points tools at it, but nothing writes to it — filling in a durable fact means the owner hand-edits YAML frontmatter. When this task is done, an agent that learns something durable and true of the profile's owner (not of the project it's currently in) can persist it with `path profile add <doc> "<text>"`, and every pointer that reaches an agent carries a standing order to do so the moment it learns such a fact — making the profile function as memory shared across agents and projects, not only a set of manually-maintained defaults.

## Context

Relevant documentation:

- [F-51, F-52](../requirements/03-functional.md#global-profile)
- [Profile and Precedence](../blueprints/07-profile-and-precedence.md) — the three existing injection mechanisms (`path profile`, `install-shims`, the neutral `AGENTS.md` line) this task adds a fourth, symmetric mechanism to
- `scripts/profile.py` — `ensure_scaffold`, `assemble`, `_managed_block`, `install_shims`
- `bin/path` — `cmd_profile`, the `profile` subparser (currently flat, no subcommands)
- `scripts/init.py` — `_agents_template`, the source of every new project's neutral pointer line
- `scripts/migrate.py` — `PROFILE_POINTER`, the same line kept for the legacy migration path

## Prerequisites

None. This project's own profile at `~/.lcp` already exists (seeded, mostly unfilled placeholders) and is not a blocker.

## Scope

- A new profile-document mutation in `scripts/profile.py`: appends a dated, attributed line to one of the four profile documents (`identity`, `working-style`, `conventions`, `stack`) and refreshes that document's `timestamp` field. Reuses `okf.load`/`okf.save` for frontmatter-safe read/write, consistent with the rest of the codebase (not hand-rolled regex).
- Rejects an unknown document name with a `ProfileError` listing the valid ones.
- Never overwrites existing body content — appends under a `## Notes` section, creating that section on first use, consistent with `ensure_scaffold`'s "never overwrite what's already there" guarantee.
- `path profile add <doc> "<text>"` wired into `bin/path` as a subcommand of the existing `profile` command. `path profile` with no subcommand keeps today's print behavior unchanged.
- The shim block (`_managed_block` in `scripts/profile.py`) gains the standing order: write a learned, durable, non-project-specific fact via the command above, the moment it's learned, never by hand-editing the file.
- The neutral `AGENTS.md` pointer line — in `scripts/init.py`'s `_agents_template`, `scripts/migrate.py`'s `PROFILE_POINTER`, and `blueprints/07-profile-and-precedence.md`'s quoted copy of it — gains the same instruction, in the same neutral, no-personal-data form.
- This repository's own `AGENTS.md` Global Profile section is updated to match (Path dogfoods itself).
- Re-run `path install-shims` once the code lands, so `~/.claude/CLAUDE.md`'s managed block actually carries the new standing order (the point of this task is moot until that happens; the command applies by default — `--dry-run` is the opt-out, there is no `--apply` flag).
- Tests in `tests/test_profile.py` covering the new mutation, mirroring the existing `ProfileFixture` pattern.

### Out of Scope

- Propagating the updated neutral line into other consumer projects' already-scaffolded `AGENTS.md` files (e.g. `lcg`) — `refresh_project` never overwrites an existing `AGENTS.md`, so there is no mechanical way to do this today, and building one is a separate, larger question about whether Path should ever touch a file it already wrote once.
- Filling in the actual content of `~/.lcp/profile/*.md` (still placeholder text) — a separate, non-Path-development task.
- A per-section targeting scheme (matching a note to one of a document's existing subsections by topic) — a flat, dated `## Notes` log is enough; topic-sorting learned facts is a judgment call better left to whoever later reads and reorganizes the doc, not the write path.
- Aider's shim (`~/.aider.conf.yml`) gets the same managed-block text automatically since it shares `_managed_block`, but this task does not add any Aider-specific testing — no Aider instance is available to verify against.

## Tasks

- [x] Add `PROFILE_DOC_ORDER`-keyed lookup and an `add_entry(lcp_home, doc, text)` function to `scripts/profile.py`, using `okf.load`/`okf.save`.
- [x] Add a `## Notes` section on first write to a given document; append subsequent entries under it.
- [x] Raise `ProfileError` for an unrecognized `doc` argument, naming the valid choices.
- [x] Add the `path profile add <doc> <text>` subcommand to `bin/path` (nested under the existing `profile` subparser; bare `path profile` unchanged).
- [x] Update `_managed_block()` in `scripts/profile.py` with the standing-order instruction.
- [x] Update `_agents_template()` in `scripts/init.py` and `PROFILE_POINTER` in `scripts/migrate.py` with the same instruction, worded identically to the shim block's, so the two texts don't drift.
- [x] Update `blueprints/07-profile-and-precedence.md`'s "Injection" section to describe the write path as a fourth mechanism, and update its quoted `AGENTS.md` line to match the new template.
- [x] Update this repository's own `AGENTS.md` Global Profile section to match the new template text.
- [x] Add tests to `tests/test_profile.py` for `add_entry`.
- [x] Run `path install-shims` once the above lands, so `~/.claude/CLAUDE.md` carries the update.

## Acceptance Criteria

- [x] `path profile add <doc> "<text>"` appends a dated line to the named document under a `## Notes` heading and updates that file's `timestamp` field, without touching any other content in the file. (Verified in unit tests against `stack.md`; verified for real against `working-style.md`.)
- [x] `path profile add nonsense "..."` exits non-zero with an error naming the four valid document names.
- [x] Calling `path profile add` twice on the same document appends two lines under one `## Notes` heading, not two headings.
- [x] `path profile` with no arguments still prints the assembled profile exactly as before.
- [x] The shim block written by `install-shims`, the `AGENTS.md` template in `scripts/init.py`, `PROFILE_POINTER` in `scripts/migrate.py`, and the quoted line in `blueprints/07-profile-and-precedence.md` all carry matching wording for the standing order.
- [x] This repository's own `AGENTS.md` reflects the new wording.
- [x] `~/.claude/CLAUDE.md`'s managed block reflects the new wording — confirmed after actually running `path install-shims`.
- [x] `python3 -m unittest discover -s tests` passes (322 tests), and `ruff check scripts/ bin/path tests/` is clean.
- [x] `path check T-024` passes.

## Validation

- [x] Unit tests: `add_entry` creates the `## Notes` heading on first call, appends without a duplicate heading on a second call, updates `timestamp`, raises `ProfileError` on an unknown doc, and never touches a document's existing sections.
- [x] Unit tests: the CLI wiring change doesn't regress `path profile`'s existing print behavior (covered by existing `TestAssemble` tests, re-run as a regression check).
- [x] Manual/integration check: ran `path profile add working-style "..."` for real against this machine's actual `~/.lcp` with a genuinely learned fact from this conversation, inspected the resulting file, then ran `path install-shims` and confirmed `~/.claude/CLAUDE.md`'s managed block updated (existing graphify block and `@RTK.md` import both preserved untouched).

## Notes

Encountered in passing, not in scope here: this task's own `path.project` frontmatter field was seeded as `code` rather than `path`, because `tasks_mod.new_task` derives it from `root.parent.name`, which assumes `root` (the `.path` directory) has the project one level up. Path's own repo is self-hosted at the top level rather than nested under `.path/` (see `AGENTS.md`), so `root` there *is* the project root and `root.parent.name` resolves to `code` (the parent of `~/code/path`) instead of `path`. Nothing currently reads a task's `project` field programmatically (`metrics.py` derives the project name independently via `okf.project_dir(root).name`), so this is latent, not load-bearing — worth its own task, not fixed here.

---

*The change log, drift log, and issues found live in this task's frontmatter, not in this body. Append to them with `path log change|drift|issue` — see `blueprints/03-conventions.md`.*

*When complete, write a `RETROSPECTIVE` build log entry naming this task's id, and update `AGENTS.md`. `path check` verifies both.*
