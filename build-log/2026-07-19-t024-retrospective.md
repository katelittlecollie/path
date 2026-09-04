---
type: Build Log Entry
title: 2026-07-19 — T-024 Retrospective
description: ''
tags: []
timestamp: 2026-07-19T00:00:00Z
path:
  date: 2026-07-19
  entry_type: RETROSPECTIVE
  related_tasks: [T-024]
---

# 2026-07-19 — T-024 Retrospective

**Type:** RETROSPECTIVE

## Summary

T-024 closed the last gap in the global profile system: the three existing injection mechanisms (`path profile`, `install-shims`, the neutral `AGENTS.md` line) were all read-only, so an agent that learned something durable about the profile's owner had nowhere to put it but the owner's own hands. `path profile add <doc> "<text>"` closes that loop — it appends a dated entry under a `## Notes` heading in the named profile document and refreshes that document's timestamp, using the same `okf.load`/`okf.save` frontmatter handling as the rest of the codebase. Every pointer that reaches an agent (the shim block, the `AGENTS.md` template, the legacy migration pointer, this repository's own `AGENTS.md`) now carries a standing order to use it the moment a durable, non-project-specific fact is learned.

## What Prompted This

Raised in conversation, not found in the backlog: the owner wants `$LCP_HOME` to become a cross-agent memory store, potentially replacing an individual agent's own private memory system entirely. Read-only access made that impossible — nothing closed the loop from "agent learns a fact" to "fact is durably recorded." Two design questions were resolved with the owner before the task was drafted, matching the Definition of Ready's ambiguity check: (1) a CLI-mediated write, consistent with "everything deterministic lives behind the CLI," over telling agents to hand-edit YAML frontmatter directly; (2) a full Path task rather than a quick, unstructured fix, per this repository's own rule that changes to Path go through its task process.

## What Went Well

Reusing `okf.load`/`okf.save` instead of hand-rolled regex kept `add_entry` small and made it get frontmatter-safety (key order, YAML formatting) for free. Piggy-backing the standing order onto the existing shim/`AGENTS.md`-line mechanisms, rather than inventing a fourth delivery channel, meant only prose changed at the injection points — the delivery plumbing (`install_shims`, `_upsert_managed_block`) needed no changes at all.

## What Was Learned

`tasks_mod.new_task`'s `project` field default (`root.parent.name`) assumes the `.path/` root's parent is the actual project directory. This repository is self-hosted at the top level rather than nested under `.path/`, so the field resolved to `code` (the parent of `~/code/path`) instead of `path` for this very task. Nothing reads that field programmatically today, so it's latent rather than load-bearing — logged as a note in T-024 rather than fixed here, and worth its own task.

The real-world integration step doubled as the feature's first real use: the fact recorded in `~/.lcp/profile/working-style.md` — that the owner wants the profile to become cross-agent memory — is itself the fact that motivated building the command that recorded it.

## Effort

Estimated at 8 (several files, real design judgment). Held — no drift logged.
