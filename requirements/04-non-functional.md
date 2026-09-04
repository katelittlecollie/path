---
type: Requirement
title: Non-Functional Requirements
description: The quality attributes Little Collie Path must hold to.
tags: [requirements, non-functional]
timestamp: 2026-07-16T00:00:00Z
---

# Little Collie Path — Non-Functional Requirements

## Human Readability

**NF-01** All documents must be plain Markdown, readable and editable with nothing but a text editor. No proprietary formats and no database-backed content.

Path's tooling is required to *write* documents correctly — it allocates identifiers, shapes frontmatter, and validates. It is not required to *read* them, and it must never become required. If the tooling disappeared tomorrow, every Path document would remain a legible Markdown file. See [Architecture](../blueprints/01-architecture.md) for why this trade was made.

**NF-02** Any document must be understandable by a technically literate person who has never seen the project before, within a reasonable reading time.

**NF-03** Acronyms and abbreviations must be defined on first use within each document.

## AI Operability

**NF-04** A task must provide enough context that an AI agent can begin execution at the start of a fresh session, without any prior conversation.

**NF-05** Documents must not assume an agent remembers previous conversations. All relevant context must be in the files.

**NF-06** `AGENTS.md` must be concise enough to read in full without consuming excessive context window budget. Every agent reads it at the start of every session, so anything that makes it longer makes every future session more expensive, permanently.

## Human Handoff

**NF-07** Any task must be completable by a human developer without AI assistance. Tasks must not rely on AI capabilities that a human could not replicate.

**NF-08** Reading and understanding Path documentation must require nothing but a text editor and a file system. Producing documents that validate requires the Path command-line tool; this is a deliberate exchange of zero-dependency authoring for mechanical verifiability, and it is bounded by NF-01.

## Maintainability

**NF-09** The overhead of maintaining Path documentation must be proportional to the complexity of the project. Simple projects should not require extensive documentation.

**NF-10** Documents must be updated as the project evolves. Stale documentation is treated as a defect.

**NF-11** When a decision is reversed or a requirement changes, the original document must be updated (not supplemented with a correction document), and a build log entry must explain the change.

## Portability

**NF-12** Path documentation must work with any version control system. All files must be plain text and diff-friendly.

**NF-13** Path must not depend on any specific operating system, cloud provider, or third-party service.

## Security

**NF-14** No credentials, secrets, tokens, or sensitive personal data must be stored in Path documentation files.

**NF-15** Cross-project interaction boundaries must be documented with explicit security considerations before any implementation begins.

## Scalability

**NF-16** The system must support multiple concurrent projects without cross-contamination of documentation.

**NF-17** Adding a new project must not require modifying any existing project's documentation.

## Tool Independence

**NF-18** Path must work with any AI coding tool, and with none. No capability may exist only inside a tool-specific integration; anything a tool-specific wrapper can do, the command-line tool must also do.

**NF-19** Tool-specific files must be pointers to the canonical `AGENTS.md`, thin enough that they carry no information of their own and therefore cannot drift from it.

**NF-20** Path must not require a network connection for any operation other than installing an optional dependency.

## Personal Data Separation

**NF-21** The global profile must live outside every project and outside the Path product repository. The product repository is public; the profile must never be committed to it.

**NF-22** No file inside a project may contain personal profile content. A project's only reference to the profile must be a location-independent pointer, safe to commit publicly.

**NF-23** Validation must scan for personal data and secrets, as a backstop against the separation in NF-21 and NF-22 being breached by accident.

## Dependencies

**NF-24** Path must degrade gracefully when an optional dependency is absent: warn, explain, and continue. Only the operations that genuinely require the missing dependency may be skipped.

**NF-25** Path must never install software without explicit confirmation from a person, and must never prompt for confirmation when no terminal is attached.

**NF-26** Path must report the true outcome of an installation it performs. A successful exit code is not evidence that a tool is present and working; that must be verified independently.
