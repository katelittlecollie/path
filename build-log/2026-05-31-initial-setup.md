---
type: Build Log Entry
title: 2026-05-31 — Initial Setup
description: ''
tags: []
timestamp: 2026-07-17T00:43:22Z
path:
  date: 2026-05-31
  entry_type: DECISION
---

# 2026-05-31 — Initial Setup

**Type:** DECISION

## Summary

Path was created as a file-based software development documentation system for Little Collie projects. This entry documents the key decisions made during the initial design session.

## Decisions

**Name: Path.** Several names were considered, including Keel (structural backbone metaphor), Heel, Harness, and Lead (dog-adjacent). Path was chosen for its neutrality and meaning — direction and progress without implying hierarchy.

**Self-documenting from the start.** Path is itself a project following Path conventions. This was a deliberate choice to validate the system using itself and to provide a canonical example of a correctly structured project.

**File-based, no tooling required.** Path is plain Markdown files. No database, no server, no UI. This keeps overhead low, makes documents portable and version-control friendly, and ensures a human can always step in without special software.

**Requirements and blueprints in multiple files, not one large document.** Split by topic to allow a reader to find relevant sections without reading everything. Named and numbered for ordering.

**CLAUDE.md as the AI entry point.** Each project has a CLAUDE.md at its root that provides orientation and a navigation map. This ensures Claude can start a work session immediately without reconstructing context from chat history.

**Projects are independent.** Each project is self-contained. Cross-project interactions must be explicitly documented before implementation.

## Initial Project Portfolio

Path was designed against a portfolio of several planned projects rather than a
single one. That is why "projects are independent" is a decision above and not an
afterthought: the conventions had to hold for a repository the author had not
written yet.

## Context

A key goal of Path is to reduce context-setting overhead in AI sessions, making
each conversation more productive. The constraint that shaped the design was a
finite per-session message budget — hence work orders that carry their own
context, and a navigation map at the project root, so a session can begin
without reconstructing history from chat.
