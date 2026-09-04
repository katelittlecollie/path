---
type: Blueprint
title: Definition of Ready
description: ''
tags: []
timestamp: 2026-07-17T00:43:22Z
---

# Path — Definition of Ready

The Definition of Ready is a checklist an AI agent or a human executor works through before beginning a task. If any item cannot be checked, stop and resolve the ambiguity before proceeding. Unresolved items should be raised as questions to the project owner — see `path decision raise`.

This document applies project-wide. Individual tasks may add their own prerequisites on top of these.

---

## Task Clarity

- [ ] I can state the objective of this task in one sentence without ambiguity.
- [ ] The scope section clearly defines what is and is not included in this task.
- [ ] All tasks in the task list are specific and actionable — none require interpretation to understand what to do.
- [ ] All acceptance criteria are verifiable — I can check each one when the work is done.
- [ ] The task's status is `pending` (not `blocked` or `complete`).
- [ ] The task has an effort estimate (Fibonacci points, see `blueprints/03-conventions.md`) assigned.

## Context and Documentation

- [ ] I have read the project's `AGENTS.md` and understand the project's current state.
- [ ] I have read all requirements and blueprint sections linked in the task's Context section.
- [ ] I understand the design decisions and constraints relevant to this task.
- [ ] I know where the source code or files I need to create or modify are located.

## Prerequisites

- [ ] Every task listed in `path.requires` is marked `complete`.
- [ ] All external dependencies (APIs, services, credentials) needed to complete the work are available and accessible.
- [ ] There are no known blocking issues that would prevent completion.

## Ambiguity Check

Before starting, consider each of the following. If the answer is "I'm not sure," raise it as a question before proceeding.

- [ ] Do I know which technology, library, or approach to use, or is there exactly one reasonable option?
- [ ] Do I know how this work connects to the rest of the system (inputs, outputs, dependencies)?
- [ ] Do I know what to do if I encounter an error or an unexpected state?
- [ ] Are there cross-project interactions involved, and if so, are the boundaries documented?
- [ ] Is there anything in the task that could be interpreted more than one way?

## Readiness Declaration

If all items above are checked, the task is ready to execute. If any item is unresolved, document the specific question or gap and surface it to the project owner (`path decision raise`) before beginning work.

---

*This document should be updated whenever recurring ambiguities reveal a gap in the checklist.*
*Last updated: 2026-07-17.*
