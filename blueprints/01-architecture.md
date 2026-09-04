---
type: Blueprint
title: System Architecture
description: How Little Collie Path is structured and why.
tags: [architecture, okf, cli]
timestamp: 2026-07-16T00:00:00Z
---

# Little Collie Path — System Architecture

## Overview

Path is a file-based documentation system. It has no server, no database, and no UI. It is a set of conventions for organizing Markdown files, expressed in the [Open Knowledge Format](./06-okf-mapping.md), with a command-line tool that makes the deterministic parts of the system mechanical rather than a matter of discipline.

## Core Concepts

### The Project Folder

Each software project using Path lives in its own folder. That folder is the single source of truth for everything about the project: what it does, how it's built, what work is in progress, and what decisions were made along the way.

The folder can live anywhere on the filesystem. It is typically version-controlled alongside or separately from the project's source code.

### The Four Document Types

**Requirements** describe *what* the system does. They are written from the perspective of users and stakeholders. They must not contain implementation details.

**Blueprints** describe *how* the system is built. They translate requirements into technical architecture, technology choices, data models, and design decisions. They must capture the reasoning behind decisions, not just the decisions themselves.

**Tasks** describe *discrete units of work* to move the system toward its target state. They are the unit of execution — handed to an AI agent or a human to complete one at a time. A task references requirements and blueprints but does not reproduce them. Tasks were called work orders before Path adopted OKF; the unit of work is unchanged, the name and the file format are not.

**Build log** captures *what happened* during development: decisions made, problems encountered, approaches tried, and lessons learned. It is the system's memory and the source of self-improvement.

### AGENTS.md

Every project has an `AGENTS.md` at its root. This file is the entry point for any AI agent — or any human unfamiliar with the project — starting a new session. It provides:

- A brief description of the project
- A navigation map to all documentation
- Instructions for executing a task
- A pointer to the current active task

It is named `AGENTS.md` rather than for any particular vendor because Path must work with any tool. Tool-specific entry files (`CLAUDE.md` and its equivalents) exist, but only as pointers thin enough to carry no information of their own and therefore unable to drift from it.

`AGENTS.md` must be short enough to read in full without significant cost to context window budget. It is a navigation guide, not a record: it should not hold more than a few lines of summary for current state, and further detail belongs in the build log.

## The Three Homes

Path's code, its user's personal data, and a project's documentation each live in exactly one place. The boundaries between them are load-bearing.

| Home | Contains | Visibility |
|------|----------|------------|
| The Path repository | The product: the CLI and the canonical documents | Public, MIT |
| `$LCP_HOME` (default `~/.lcp`) | The personal profile, machine config, cached state | Private |
| A consumer project | Documentation only | Whatever the project is |

**A consumer project contains no Path code.** This is the sharpest departure from Path's earlier design, which copied its scripts into every project it initialized. Those copies began drifting from the originals immediately, and a substantial part of the system existed only to detect that drift and raise work orders to repair it. Removing the copies removed the entire problem: there is now one copy of the tool, on `$PATH`, and nothing left to drift from.

**The profile is separate from the product.** This repository is public; a personal profile cannot live in it. See [Profile and Precedence](./07-profile-and-precedence.md).

## The CLI as the Deterministic Layer

Path divides work by whether getting it wrong is a matter of fact or a matter of judgment.

**Deterministic work belongs in code.** Allocating a task identifier, shaping frontmatter, enforcing legal status transitions, appending a structured log entry, computing metrics, validating a completion claim, migrating a project. None of this benefits from an agent's creativity, and all of it is quietly corrupted by an agent's improvisation. It lives in the `path` command.

**Judgment work belongs in prose.** Writing an objective worth executing, deciding what is in scope, reviewing logged issues for the process gap that let them through. No script can do this. It lives in the documents, where an AI or a human reads it and thinks.

Tool-specific wrappers are thin: they call the CLI, then apply judgment where the CLI's output asks for it. This is what keeps Path tool-agnostic — a wrapper is a convenience, never a capability.

### The Dependency Trade, Stated Honestly

Path's earlier architecture claimed no runtime dependencies: just Markdown, enforced by discipline. That claim is now partly false, and it was given up deliberately rather than allowed to erode.

What was bought: metrics that come out of frontmatter with a standard query tool instead of a regular expression scraping prose; completion claims that are mechanically verified instead of trusted; identifiers and status transitions that cannot be improvised.

What was sold: producing a valid Path document by hand is harder than it was. Frontmatter is less pleasant to hand-edit than a Markdown bullet, and that cost falls on the human.

The boundary that keeps this honest is [NF-01](../requirements/04-non-functional.md): **the tooling is required to write documents correctly, never to read them.** Every Path document remains a legible Markdown file if the tool vanishes. A system that could not be read without its tooling would be a database wearing Markdown as a costume, and that is the line Path does not cross.

## Project Independence

Projects are independent units. A project's documentation must be self-contained and must not require reading another project's documentation to understand.

Cross-project interactions (shared authentication, API integrations, shared libraries) must be explicitly documented in each participating project's blueprints. The integration contract — including data formats, security boundaries, and failure modes — must be written before implementation begins.

The global profile is the sole exception to independence, and it is deliberately a weak one: it is referenced rather than copied, and any project overrides it on conflict.

## The Knowledge Graph

Initializing or refreshing a project also builds a knowledge graph of it, using the `graphify` command-line tool. The graph is a derived artifact: regenerated rather than edited, and never committed.

Path calls graphify's CLI rather than any tool-specific integration of it, for the same reason `AGENTS.md` is not named for a vendor. The graph is optional — its absence warns and continues, and never fails an operation.

`path install` and `path update` check for graphify and, if it is missing or older than the configured floor, offer to install it. Installing software is a side effect, so the offer is never silent and never assumed: the default answer is no, nothing is attempted without a terminal attached to ask, and a decline is remembered so Path stops asking. The CLI is `graphify`; the PyPI package is `graphifyy` — two y's — and getting that backwards is the easiest way to break this quietly, so `scripts/graphify_check.py` names both explicitly rather than deriving one from the other.

## Path Itself

Path is documented using Path conventions. This repository is a first-class Path project with requirements, blueprints, tasks, and a build log. Changes to Path's conventions are made through Path's own task process.

## What Path Is Not

Path is not a project management tool. It measures effort and drift to improve its own process, and it projects its own remaining backlog against its own recent rate — but it does not measure a person's or a team's capacity, and it never will.

That second clause is a revision, and the original position is worth stating so the change is legible: Path used to refuse rate entirely, on the reasoning that a velocity figure invites comparison between people and periods, and that a tool which offers the number is responsible for what gets done with it. Half of that reasoning survived. Projecting a backlog against the rate at which that same backlog has lately been consumed answers a question the owner of the backlog is entitled to ask, and the data — completion dates and effort points — was already recorded and already published. Refusing to divide two numbers Path had itself written down was not restraint; it just moved the arithmetic into someone's head, where it lost its provenance on the way.

What did not change is the boundary. The figure describes the backlog, never the worker. There is no per-person breakdown, no per-agent breakdown, and no period-over-period comparison, and `path check` would have nothing to say about any of them because Path does not record who was fast. The reversal and its limits are in [the decision](../build-log/2026-09-04-forecasting-the-backlog.md).

Path is not a ticketing system. Tasks do not replace a bug tracker for production systems.

Path is not a communication tool. It does not replace conversation — it replaces the need to reconstruct context from conversation.
