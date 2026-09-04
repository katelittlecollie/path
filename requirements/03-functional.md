---
type: Requirement
title: Functional Requirements
description: What Little Collie Path must do.
tags: [requirements, functional]
timestamp: 2026-07-16T00:00:00Z
---

# Little Collie Path — Functional Requirements

## Project Structure

**F-01** Every software project using Path must have a dedicated root folder containing all Path documentation for that project.

**F-02** Each project folder must contain an `AGENTS.md` file at its root that serves as the AI navigation guide, providing orientation and a map to all documentation. Tool-specific entry files (`CLAUDE.md`, `CONVENTIONS.md`, and equivalents) must be pointers to `AGENTS.md`, never copies of it.

**F-03** Each project folder must contain a `.path/` subdirectory holding four further subdirectories: `requirements/`, `blueprints/`, `tasks/`, and `build-log/`. `.path/` is a dotfile so that it reads as tooling rather than project content and cannot collide with a project's own use of the plain name `path`. The Path repository itself is the sole documented exception, self-hosting these four directories at its own top level — see `blueprints/01-architecture.md`.

**F-04** Projects must be independent of each other. A project's documentation must not depend on another project's documentation to be understood.

**F-05** Cross-project interactions, if any, must be explicitly documented in the relevant projects' blueprints, including security boundaries and integration contracts.

## Requirements Documents

**F-06** Requirements must be split across multiple focused Markdown files within the `requirements/` folder, organized by topic.

**F-07** Requirements files must be numbered for ordering (e.g., `01-overview.md`, `02-user-stories.md`) but the number of files and their topics are determined per project.

**F-08** Requirements must include at minimum: an overview, user stories, functional requirements, and non-functional requirements.

## Blueprint Documents

**F-09** Blueprints must be split across multiple focused Markdown files within the `blueprints/` folder, organized by topic.

**F-10** Blueprints must translate requirements into technical architecture, design decisions, and implementation constraints.

**F-11** Blueprints must include at minimum: system architecture and folder/structure conventions relevant to that project.

**F-12** Blueprint documents must capture the *why* behind design decisions, not just the decision itself.

## Tasks

Tasks were called work orders before Path adopted OKF. The unit of work is unchanged; the name and the file format are not. See [OKF Mapping](../blueprints/06-okf-mapping.md).

**F-13** Tasks must be individual Markdown files in the `tasks/` folder, one file per task, named `T-NNN-[short-slug].md`.

**F-14** Tasks must be atomic — each must represent a discrete, completable unit of work.

**F-15** Tasks must be self-contained — an executor (human or AI) must be able to complete the task using only the task itself plus the linked requirements and blueprint sections.

**F-16** Tasks must include: objective, context with links to relevant docs, prerequisites, in-scope tasks, out-of-scope items, and acceptance criteria.

**F-17** Tasks must carry a status in frontmatter at `path.status`, one of: `pending`, `in-progress`, `complete`, or `blocked`.

**F-18** A task template (`TASK-TEMPLATE.md`) must be maintained in the `tasks/` folder.

**F-19** The `AGENTS.md` file must always indicate the current active task, if any, in exactly one line.

**F-53** Path must support grouping tasks into execution batches, so that a set of tasks intended to be executed together can be named, ordered, and completed as one unit. A batch must be a document of its own; a task must belong to at most one batch, and belonging to none must remain the ordinary case.

**F-54** Batch membership must be recorded on the task at `path.batch`, and the batch document must record only the intended execution order at `path.sequence`. A batch's status and completion date must be derived from its members at read time and must never be stored, for the same reason a decision's age is never stored.

**F-55** The generated `tasks/index.md` must group tasks by whether they can be started, so that a reader who opens the file without running anything can see what is available to work on. The grouping must remain a pure function of the directory, and the file must remain free of frontmatter as OKF requires of a reserved index. The project status page must present the same queue, so that neither surface requires a terminal to answer what is next.

## Build Log

**F-20** The build log must capture decisions made, problems encountered, and resolutions reached during development.

**F-21** Build log entries must be individual Markdown files named by date and topic (e.g., `2026-05-31-initial-setup.md`).

**F-22** Build log entries must be written at the time of the decision or event, not reconstructed later.

**F-23** The build log must feed back into requirements and blueprints — when a log entry reveals a recurring pattern or a better approach, the relevant documents must be updated.

## Path as a Project

**F-24** Path itself must be documented using Path conventions. The Path repository is a first-class project.

**F-25** Improvements to Path's own templates and conventions must be reflected in Path's blueprints and, where appropriate, propagated to existing projects.

## OKF Compliance

**F-26** Every Path document must be a valid OKF concept: a Markdown file whose YAML frontmatter parses and contains a non-empty `type` field. The reserved filenames `index.md` and `log.md` are exempt and must instead follow OKF's prescribed structure for those files.

**F-27** Path must use the type vocabulary defined in [OKF Mapping](../blueprints/06-okf-mapping.md): `Task`, `Batch`, `Requirement`, `Blueprint`, `Build Log Entry`, `Decision Log`, and `Profile`.

**F-28** All Path-specific frontmatter fields must live under a single `path:` mapping, so that they cannot collide with fields defined by a future version of OKF.

**F-29** Path must preserve unknown frontmatter keys when reading and rewriting any document, as OKF requires of consumers.

**F-30** A task's change log, drift log, and issues found must be recorded as structured lists in frontmatter. They must not also exist as prose sections in the body — one fact, one location.

**F-31** The decisions log must record each decision as a structured frontmatter row. The age of a decision must be computed from its `raised` and `resolved` dates at read time and must never be stored.

## Metrics

**F-32** Every Path metric must be derivable from frontmatter alone, using a standard query tool, without executing any Path-supplied parser. A tool that extracts frontmatter before querying it satisfies this; see [OKF Mapping](../blueprints/06-okf-mapping.md#metrics-from-frontmatter) for the verified invocations and the traps that make the naive one wrong.

**F-33** Path must provide a command that assembles all metrics into a single machine-readable document.

**F-34** The project status page must be generated from that metrics document, not by parsing document bodies.

**F-56** Path must derive a completion rate from recorded completion dates and effort over a declared trailing window, and project the remaining backlog against it. The window must be stated wherever the figure is shown. When the window holds too few completions to support a projection, Path must say so and must not widen the window silently, because a figure whose basis moved without saying so is worse than no figure. A projection resting on any model-assigned effort or inferred completion date must be marked as derived, exactly as the burn-up already is.

**F-57** The rate and the projection must describe the remaining backlog only. Path must not present them as a measure of a person's or a team's capacity.

## Tooling

**F-35** Path must provide a single command-line entry point that performs every deterministic operation: creating a task, changing its status, appending a log entry, raising or resolving a decision, validating, reporting metrics, and migrating a project.

**F-36** Task identifiers must be allocated by the tooling and must be sequential. An identifier that any document refers to must never be reused, so that no identifier in the build log's history can describe two different pieces of work. An identifier belonging to a task deleted before anything referenced it may be reused, since no history exists to make ambiguous.

**F-37** The tooling must reject an illegal status transition and must ensure a task's `completed` date is set if and only if its status is `complete`.

**F-38** Consumer projects must not contain any Path code. The tooling lives with the Path product and is invoked from the user's `$PATH`.

**F-39** Path must work with any AI tool or none. No capability may be available only through a tool-specific integration.

**F-58** A task must be readable as ready or not ready from frontmatter alone: ready when it is pending and every task named in `path.requires` is complete. Path must provide a command that names the next task to start, and the next batch, without the caller reading every task file.

**F-59** Path must provide batch-scoped forms of the operations that would otherwise be repeated once per member: starting a batch, completing a batch, and validating a batch. A batch's completion claim must be validated to the same standard as each of its members individually.

## Proof of Done

**F-40** Path must provide a validation command that mechanically verifies a task's completion claim and exits non-zero on failure, so that a completion claim is verifiable rather than trusted.

**F-41** Validation must check at minimum: frontmatter validity, that the identifier matches the filename, status and date consistency, that the effort estimate is on the defined scale, that prerequisite tasks are complete, that referenced requirement identifiers exist, that relative links resolve, that a `RETROSPECTIVE` build log entry declares the task in its `path.related_tasks`, that a completed task's Tasks and Acceptance Criteria sections have no box left unchecked, that `AGENTS.md` navigation fields are one line each, and that a batch's recorded sequence names exactly the tasks that claim membership in it, and that no secrets or placeholder markers remain.

**F-42** The result of a validation run must be recorded in the task's frontmatter and must be written only by the tooling.

## Global Profile

**F-43** Path must support a global, personal profile stored outside every project, at a location that defaults to `~/.lcp` and is overridable by the `$LCP_HOME` environment variable.

**F-44** Profile content must reach an AI tool by reference. Personal information must never be copied into a project's files.

**F-45** Path must provide a command that prints the assembled profile to standard output, so that any tool capable of running a command can consume it.

**F-46** A project's own documentation must override the global profile on any conflict. A project that contradicts a global rule must document the override deliberately; validation must report an undocumented contradiction.

**F-51** Path must provide a command that appends a durable, cross-project preference to a named profile document and refreshes that document's timestamp, so an agent can persist what it learns about the profile's owner without hand-editing YAML frontmatter.

**F-52** Every pointer that reaches an agent — the shim block and the project `AGENTS.md` line — must instruct it to persist a learned, durable, non-project-specific fact via that command at the moment it is learned, so the profile can serve as memory shared across agents and projects rather than only a read-only default.

## Knowledge Graph

**F-47** Initializing or refreshing a project must also build or update its knowledge graph, by invoking the graphify command-line tool rather than any tool-specific integration of it.

**F-48** The graph must be updated incrementally when one already exists, and built in full only on first run.

**F-49** Path must check for graphify when installing or updating, and must offer to install it. Installation must not proceed without explicit confirmation, must never be attempted when no terminal is attached, and a declined offer must be remembered.

**F-50** The absence of graphify must never cause a Path operation to fail. Path must warn and continue.
