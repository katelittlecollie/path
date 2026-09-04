---
type: Blueprint
title: Definition of Done
description: The completion checklist, and which items a machine can verify.
tags: []
timestamp: 2026-07-17T00:43:22Z
---

# Path — Definition of Done

The Definition of Done is a checklist an AI agent or a human executor works through before marking a task `complete`. Every item must be checked. If an item cannot be checked, document why in the build log and surface it to the project owner.

This document applies project-wide and defines the minimum standard for all completed work. Individual tasks will have their own acceptance criteria in addition to these.

Every item below is tagged **[Mechanical]** or **[Judgment]**. This is not decoration — it is the contract between `path check` and whoever closes the task:

- **[Mechanical]** items are verified by `path check` and, in aggregate, by `path close`. A machine answering a question of fact does not need a person to also answer it; that would just be trusting the same claim twice.
- **[Judgment]** items cannot be reduced to a fact a script can check — they require understanding the work, not just its shape. `path close` cannot verify these, so it does not pretend to. It lists them, and the closing agent or human works through the list explicitly, in the session-close entry, rather than the list being silently skipped because nothing enforced it.

A task is not done because `path check` passed. It is done because `path check` passed *and* every Judgment item was actually considered. The mechanical half exists so the judgment half gets a person's or an agent's full attention instead of also being where the mechanical mistakes hide.

---

## Task Completion

- [ ] **[Mechanical]** Every item in the task's `## Tasks` section is checked off.
- [ ] **[Judgment]** Every acceptance criterion is not merely checked off but actually met and verifiable — the box being ticked is a claim, not proof.
- [ ] **[Judgment]** Any code created achieves the project's required level of code coverage and all tests pass. (Verified by the project's own CI jobs — lint, compile, test — which are project-specific and outside `path check`'s scope.)
- [ ] **[Judgment]** The work has been reviewed by a human being.
- [ ] **[Mechanical]** The task's status has been updated to `complete`, with `path.completed` set.

## Code and File Quality

- [ ] **[Judgment]** All files created or modified are in the correct location per the project's folder structure blueprint.
- [ ] **[Mechanical]** No credentials, secrets, API keys, tokens, or sensitive personal data appear in any Path document. (A backstop for Path's own documentation, per NF-23 — not a substitute for the project's own secret scanning across its full codebase.)
- [ ] **[Judgment]** File and directory names follow the naming conventions in `blueprints/02-folder-structure.md`.
- [ ] **[Mechanical]** No placeholder content or bare TODO/FIXME/XXX markers remain in Path documents unless explicitly noted in the task. (Application code is covered by the project's own CI, not `path check`.)
- [ ] **[Judgment]** All new code passes a linting check appropriate for the project without errors.
- [ ] **[Judgment]** All new code compiles (or parses) without errors.
- [ ] **[Judgment]** All code changes, including the task itself, have been checked in to a git-based repo with a descriptive commit message.

## Consistency

- [ ] **[Judgment]** The work is consistent with the architecture described in the project's blueprints.
- [ ] **[Judgment]** Any deviations from the blueprints are intentional and documented in the build log.
- [ ] **[Mechanical, partial]** Every task this one `requires` is itself complete. This is a narrower, structural proxy for "does not contradict prior work" — it catches an impossible dependency order, not a substantive contradiction.
- [ ] **[Judgment]** The work does not otherwise break or contradict anything established in prior completed tasks.

## Documentation

- [ ] **[Mechanical]** A build log entry of type `RETROSPECTIVE` names this task's id in its `path.related_tasks`. One entry may close a whole batch; `path new retrospective --for B-NNN` fills the list in, because which tasks an entry closes is a fact and only what was learned is judgment.
- [ ] **[Judgment]** If any new requirements were discovered during execution, they are documented (in the requirements files or as a note to the project owner).
- [ ] **[Judgment]** If any blueprint decisions were made or changed during execution, the relevant blueprint file has been updated and a `CHANGE` entry written in the build log.
- [ ] **[Mechanical]** `AGENTS.md`'s Current Task and Project Status fields are each within their one-line limit.
- [ ] **[Judgment]** `AGENTS.md` actually reflects the completed task and points at the next pending one, if any — the one-line *limit* is mechanical; that the line is *correct* is judgment.
- [ ] **[Mechanical]** If this task is in a batch, the batch's `path.sequence` and its members' `path.batch` still agree, and the batch stores no derived `status` or `completed`.

## Handoff Readiness

- [ ] **[Judgment]** A human developer with no prior context could read the delivered files and understand what was built.
- [ ] **[Judgment]** The project is in a coherent, consistent state — not left mid-task or in a transitional condition.

---

## What `path check` Actually Verifies

For completeness, the full mechanical surface, all in `scripts/check.py`: OKF frontmatter validity; the task id matches its filename; status is a legal value; effort is a Fibonacci number; `created`/`updated`/`completed` are present, well-formed, and consistent with status; `implements` references real requirement ids; `requires` references real tasks and, if this task is complete, that they are too; relative links resolve; a task's body carries no leftover `## Change Log` / `## Drift Log` / `## Issues Found` section (that data lives in frontmatter only); no unchecked box remains in `## Tasks` or `## Acceptance Criteria` when complete; a `RETROSPECTIVE` build log entry names the task in `path.related_tasks`; a batch document's `path.sequence` names exactly the tasks claiming membership in it, carries no stored `status` or `completed`, and references only tasks that exist; a task's `path.batch` names a batch that exists; no placeholder markers or likely secrets remain; `AGENTS.md`'s two hard-limited fields are within their line limit.

Everything on this list is a fact. Nothing on this list is an opinion about whether the work is good.

---

*This document should be updated whenever completed work is later found to have deficiencies not covered by the existing checklist, or whenever a Judgment item turns out to be mechanically checkable after all.*
*Last updated: 2026-07-17.*
