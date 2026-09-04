---
type: Requirement
title: Overview
description: ''
tags: []
timestamp: 2026-07-17T00:43:22Z
---

# Path — Overview

## What Is Path?

Path is a file-based software development documentation system created by Little Collie. It provides a structured, repeatable process for building software projects using AI assistance, with enough clarity that a human can step in at any point.

Path is itself a project that follows its own conventions. Every Little Collie software project that uses Path gets its own folder containing the same four document types: requirements, blueprints, work orders, and a build log.

## Why Path Exists

Building software with AI assistance is powerful but informal by default. Context lives in chat history, decisions aren't traceable, and returning to a project after a gap requires expensive reconstruction. Path solves this by:

- Externalizing context into structured, persistent files
- Making requirements and architecture decisions explicit and findable
- Enabling AI agents (Claude) to execute work orders without prior conversation context
- Allowing human collaborators to understand, review, or take over any task
- Creating a build log that feeds back into future requirements and blueprints

## Design Principles

**Separation of concerns.** Each project is independent. Cross-project interaction is possible but must be explicitly designed and documented for security and system integrity.

**Self-documenting.** Path uses Path. The system is its own best example.

**Human-readable and human-operable.** All documents are plain Markdown. No special tooling is required to read, write, or understand them. A person should be able to pick up any work order and complete it without AI assistance.

**Low overhead.** The system should be light enough that maintaining it doesn't become a project in itself. Documents are written to be useful, not comprehensive for its own sake.

**Portable and version-control friendly.** Path is just files. It works with any version control system and any editor.

## Scope of This Document Set

This document set covers Path itself — the system for managing Little Collie software projects. Individual projects built using Path will have their own requirements documents.
