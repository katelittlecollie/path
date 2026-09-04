---
type: Build Log Entry
title: '2026-06-04 — Path: Project Summary'
description: ''
tags: []
timestamp: 2026-07-17T00:43:22Z
path:
  date: 2026-06-04
  entry_type: DECISION
---

# 2026-06-04 — Path: Project Summary

**Type:** DECISION

## What Is Path?

Path is a file-based, AI-native project documentation system built by Little Collie. It gives every software project a structured, traceable set of documents — requirements, blueprints, work orders, and a build log — that an AI agent or human developer can pick up and act on without prior context. Path is itself a project documented using Path conventions.

## What Was Built

### Document Structure
Every project initialized with Path gets a `path/` subdirectory containing:

- **`requirements/`** — multiple focused Markdown files covering overview, user stories, functional requirements, and non-functional requirements. Split by topic so a reader can find what they need without reading everything.
- **`blueprints/`** — multiple focused Markdown files covering architecture, folder structure, document conventions, Definition of Ready, and Definition of Done. Captures not just decisions but the reasoning behind them.
- **`work-orders/`** — atomic, self-contained task files. Each work order includes objective, context with links to relevant docs, scope, tasks, and acceptance criteria. Designed so Claude can execute from a cold start.
- **`build-log/`** — one file per decision, problem, resolution, or session close. The system's memory and self-improvement mechanism.

A `CLAUDE.md` file at the project root serves as the AI navigation guide and entry point for every session.

### Scripts
Three shell scripts live in `path/scripts/` and are available in every initialized project:

- **`path-init.sh`** — scaffolds a new project with the full folder structure, stub documents, Definition of Ready/Done copied from Path, the work order template, scripts, and Claude slash commands. Handles existing directories gracefully, blocks on existing `path/` subdirectory, and prompts on CLAUDE.md conflicts.
- **`path-status.sh`** — shows project status from the project root (phase, current work order, work order counts by status, pending queue) or a portfolio overview from a parent directory.
- **`path-session-close.sh`** — creates a SESSION-CLOSE build log entry template to capture what was done, current state, and next-session starting point.

### Claude Slash Commands
Each initialized project gets `.claude/commands/path-status.md` and `.claude/commands/path-session-close.md`, making `/path-status` and `/path-session-close` available as slash commands in Claude/Cowork sessions — scoped to that project only.

---

## Comparison to a Hosted Platform

Path was scoped against the commercial alternative: a hosted, cloud-based
requirements-and-work-order platform with its own UI and a structured validator.
The comparison is recorded because it is what set Path's boundaries, not because
the two are interchangeable.

| Dimension | Path | Hosted platform |
|-----------|------|-----------------|
| **Cost** | Free (open source, just files) | Per-seat subscription |
| **Storage** | Local filesystem, version-control friendly | Cloud-hosted |
| **UI** | None — plain Markdown, Obsidian-friendly | Purpose-built web UI |
| **Core concepts** | Requirements, blueprints, work orders, build log | Requirements, blueprints, work orders, validator |
| **Validator / feedback loop** | Build log (manual) | Dedicated validator feature (structured feedback → tasks) |
| **AI integration** | CLAUDE.md + slash commands | Native to that platform |
| **Portability** | Fully portable — any editor, any VCS, any AI agent | Tied to the platform |
| **Customization** | Full — edit any template, convention, or script | Constrained by the platform |
| **Human handoff** | First-class — work orders are designed for human execution | Primarily AI-oriented |
| **Session continuity** | SESSION-CLOSE build log convention + path-status | Handled by the platform |
| **Self-documenting** | Yes — Path uses Path | No |
| **Multi-project portfolio** | Yes — path-status portfolio view | Yes |

### Key Differences in Philosophy

**A hosted platform** is a product: UI, cloud storage, and a structured validator
that closes the loop between user feedback and development tasks. It is designed
for teams and is polished out of the box.

**Path** is a convention system — it's just files and scripts. It trades the
validator's structure and the UI's convenience for zero cost, full portability,
and complete ownership. The build log plays the role the validator plays, but it
requires human discipline rather than platform enforcement.

The most significant gap is the validator. A platform with a formal mechanism for
turning user feedback, bug reports, and performance issues into structured,
tracked tasks has something Path does not: Path's build log captures decisions and
problems but has no formal feedback-to-work-order pipeline. This is a known gap
and a candidate for a future Path work order.

### Why Path

- No per-seat cost
- Works with an AI assistant at any subscription tier
- Documentation lives in the same repo as the code (or alongside it)
- No vendor lock-in — works with any AI agent that can read files
- Customizable to a specific workflow and set of preferences
- The system itself is improvable through its own process
