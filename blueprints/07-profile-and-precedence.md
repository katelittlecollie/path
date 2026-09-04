---
type: Blueprint
title: Profile and Precedence
description: How the global personal profile is stored, injected into any AI tool, and overridden by project rules.
tags: [profile, precedence, configuration]
timestamp: 2026-07-16T00:00:00Z
---

# Little Collie Path — Profile and Precedence

Path documents projects. It also needs somewhere to record facts about the *person* working on them — who they are, how they want to work, what they prefer by default — so that every project does not have to relearn it. That information is global, personal, and must never live inside a project.

## Why the Profile Lives Outside Every Project

A project's documentation is committed, shared, and often public. A personal profile is none of those things. Mixing them creates two problems at once: personal information leaks into repositories where it does not belong, and projects become unusable by anyone who is not the profile's owner.

The Path product repository is itself public and MIT-licensed, which makes the separation load-bearing rather than tidy-minded. The scripts in this repository *are* the product and belong here. Nothing about Kate belongs here.

## The Three Homes

| Location | Contains | Visibility |
|----------|----------|------------|
| The Path repository | The product: the CLI, the canonical documents | Public |
| `$LCP_HOME` (default `~/.lcp`) | The personal profile, config, cached state | Private, never committed |
| A consumer project | Documentation only — no Path code, no personal data | Whatever the project is |

`$LCP_HOME` defaults to `~/.lcp` and is overridable. Anyone using Path can point it wherever they like; nothing hard-codes the default.

## `$LCP_HOME` Layout

```
~/.lcp/
  config.yml            # preferences, default project root, graphify on/off, shim targets
  profile/
    index.md            # OKF index — no frontmatter, links the concepts below
    identity.md         # type: Profile — who, role, organisational context
    working-style.md    # type: Profile — how AI should work with this person
    conventions.md      # type: Profile — personal defaults: lint, style, commit format
    stack.md            # type: Profile — preferred tools and languages
  state/
    graphify/           # cached graphs, if ever centralised
```

Profile files are ordinary OKF concepts with `type: Profile`, so the same tooling that reads a project reads the profile. See [OKF Mapping](./06-okf-mapping.md).

## Injection: A Pointer, Never a Copy

The profile reaches an AI tool by reference. **No personal content is ever copied into a project repository**, because a copy is a leak waiting to be committed and a second source of truth waiting to go stale.

Four mechanisms, in order of generality:

**`path profile` prints the assembled profile to stdout.** This is the tool-agnostic path and the one that always works. Any agent that can run a command can read the profile — including piping it into a local model that has no configuration system at all.

**`path install-shims` writes per-tool pointer files, all outside any project.** Each is a few lines directing that tool at `$LCP_HOME/profile/index.md`: `~/.claude/CLAUDE.md` for Claude Code, a `read:` entry in `~/.aider.conf.yml` for Aider, and equivalents for other tools as their conventions stabilise. The shims are pointers, so the profile has exactly one home.

**Each project's `AGENTS.md` carries one neutral line.** It contains no personal data and is safe to commit publicly:

> Global profile: if `$LCP_HOME` is set, read `$LCP_HOME/profile/index.md` (or run `path profile`). Anything in this repository overrides it.
>
> Standing order: when you learn something true of the project owner, not this project — a working preference, a stack default, a personal convention — persist it immediately with `path profile add <doc> "<text>"` (`doc`: identity, working-style, conventions, or stack). Never hand-edit the profile files.

That line is the entire footprint of the profile system inside a project.

**`path profile add <doc> "<text>"` writes back (F-51).** The first three mechanisms are read-only — an agent learns a preference and has nowhere to put it but the owner's own hands. This one closes the loop: it appends a dated line under a `## Notes` heading in the named document and refreshes that document's `timestamp`, using the same frontmatter-safe read/write (`okf.load`/`okf.save`) as everything else in this codebase — never hand-rolled YAML editing. The standing order in the shim block and the `AGENTS.md` line above is what actually gets this used (F-52): without an explicit instruction to write the moment a fact is learned, an agent has no reason to reach for a command it wasn't told exists.

## Precedence: Project Beats Global

The profile is a set of defaults. **Any project's own documentation overrides it on conflict.** A project with a lint rule that contradicts a personal preference is not a mistake to be corrected — the project wins, every time.

Stating the rule is not enough to enforce it, and it is worth being clear about why. Tools load their global configuration unconditionally: Claude Code reads `~/.claude/CLAUDE.md` at the start of every session with no knowledge of whether a project override exists. The global rule arrives in context whether or not the project agrees with it.

So precedence is defended in three places rather than one:

1. **The profile files themselves open by saying so** — every `type: Profile` document begins by stating that it holds defaults and that any project's documentation overrides them. The rule travels with the content that would otherwise win by default.
2. **Each project's `AGENTS.md` restates it** in the pointer line above, so an agent reading the project learns the precedence from the project.
3. **`path check` flags silent contradictions.** A project that conflicts with a global rule must do so deliberately, in writing, in its blueprints. An undocumented conflict is reported.

**This is convention plus a check, not mechanical enforcement, and it cannot be made mechanical across tools that Path does not control.** It is the weakest guarantee in the system. Anyone relying on it should know that.

## Configuration

`~/.lcp/config.yml` holds machine-local preferences:

```yaml
project_root: ~/code           # where projects live
graphify: ask                  # on | off | ask
graphify_min_version: 0.8.0    # version floor for the dependency check
shims:                         # which per-tool pointers to maintain
  - claude
  - aider
```

Configuration is preferences, not knowledge. Anything an AI should *read* belongs in `profile/` as an OKF concept; anything that changes how the CLI *behaves* belongs here.

## Shell Setup

One line in `~/.zshrc` or `~/.bashrc`:

```bash
export LCP_HOME="$HOME/.lcp"
```

The CLI installs into `~/.local/bin`, which is conventionally already on `$PATH`. Path deliberately does not ask anyone to add a new `$PATH` entry: the previous version of this system did, almost nobody did it, and the instruction quietly rotted.

`path doctor` reports whether `$LCP_HOME` is set, whether the CLI resolves, and whether the shims are current.
