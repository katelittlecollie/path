# Little Collie Path

Path is a file-based software development documentation system for building software with or without AI assistance. It gives every project a structured, traceable set of documents — requirements, blueprints, tasks, and a build log — that an AI agent or a human developer can pick up and act on without prior context.

Every document is an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) concept: Markdown with YAML frontmatter, readable with a text editor and queryable with standard tools.

Path is built by [Little Collie](https://littlecollie.com) and is itself documented using Path conventions.

## How It Works

Every project using Path gets a `.path/` subdirectory containing four document types. Dotted deliberately — the same convention as `.git` or `.github`: it reads as tooling, not project content, and can't collide with a project's own source tree wanting to use the plain name `path`.

- **Requirements** — what the system does, for whom, and why
- **Blueprints** — how it's built: architecture, structure, and design decisions
- **Tasks** — discrete, self-contained units of work ready to hand to an AI agent or a developer
- **Build log** — a running record of decisions made, problems encountered, and lessons learned

An `AGENTS.md` at the project root is the entry point for any AI agent starting a session. It is named for no vendor because Path works with any tool — Claude Code, Aider, Cursor, Copilot, a local model, or none at all. Tool-specific files like `CLAUDE.md` are one-line pointers to it, thin enough that they carry no information of their own and therefore cannot drift.

## What Makes It Different

**Metrics come out of the files, not out of a parser.** Effort, status, change history, and drift live in frontmatter at documented locations. You can read them with `yq` without running anything Path wrote.

**Completion is checkable, not trusted.** `path check` mechanically verifies a completion claim: dates consistent, links resolving, prerequisites complete, a retrospective actually written. It exits non-zero when the claim isn't true.

**Consumer projects contain no Path code.** There is one copy of the tool, on your `$PATH`. Nothing gets copied into a project, so there is nothing to drift.

**What to do next is computed, not searched for.** A task is ready when it is pending and every prerequisite it names is complete — two fields Path already writes. `path next` names it; `tasks/index.md` is regenerated grouped by what can be started, so opening the file answers the same question with no tooling at all. Tasks that belong together become a batch, and a batch pays one round of completion bookkeeping instead of one per member.

**The forecast says what it rests on, or says nothing.** `path status` projects the remaining backlog against the rate of the last fourteen days, names that window, and marks the figure derived when it leans on an estimate. Below two completions in the window it prints a refusal rather than a number, and never widens the window to find data. It describes the backlog, never a person.

## Setup

### 1. Clone

```bash
git clone https://github.com/katelittlecollie/path.git ~/code/path
```

### 2. Put the CLI on your `$PATH`

```bash
ln -s ~/code/path/bin/path ~/.local/bin/path
```

`~/.local/bin` is conventionally already on `$PATH`.

### 3. Requirements

- **Python 3** with **PyYAML** — `python3 -m pip install --user pyyaml`
- **git** — `path migrate` reads history
- **[mikefarah's `yq`](https://github.com/mikefarah/yq)** (optional) — only to query frontmatter yourself. Two unrelated tools share the name `yq`; the other cannot read these files at all. See `blueprints/06-okf-mapping.md`.
- **[graphify](https://pypi.org/project/graphifyy/)** (optional) — `path .` builds a knowledge graph when it is installed, and offers to install it when it is not. Its absence never fails an operation.

### 4. The global profile (optional)

```bash
export LCP_HOME="$HOME/.lcp"     # in ~/.zshrc or ~/.bashrc
```

Personal preferences — how you work, your defaults — live in `$LCP_HOME/profile/`, outside every project and outside this repository. Any project's own documentation overrides them on conflict. See `blueprints/07-profile-and-precedence.md`.

### 5. Optional: a `path` skill for your agent harness

`AGENTS.md` already documents the CLI, so any agent that reads it can run `path`. To make it a first-class, model-invocable skill — surfaced by name in Claude Code, opencode, and the like — symlink the one skill file this repo ships into each harness's skills directory:

```bash
ln -sfn ~/code/path/.claude/skills/path ~/.claude/skills/path            # Claude Code
ln -sfn ~/code/path/.claude/skills/path ~/.config/opencode/skills/path   # opencode
```

**Symlink, don't copy — and this stays true for any skill added here.** The `path` skill only shells out to the CLI and prints its output: it carries no harness-specific dispatch (no Agent-tool vs `@mention`, no per-platform Python-path detection). So one canonical file serves every harness, and a symlink guarantees they cannot drift apart — the same "one copy, nothing to drift" rule the CLI itself follows.

The contrast is a skill like graphify, which *does* fork per platform because it dispatches subagents differently on each. That kind of skill is deliberately two files and must not be collapsed to one. The test before symlinking a new skill: if its body would read identically on every harness, keep it single-source; if it must name a harness's dispatch or runtime, it forks.

## Using Path

After `path .`, the project is ready for you to define what you want to build: a new system, or a better description of one that already exists. What Path generates is ordinary Markdown, editable by hand at any time; the documents in this repository are the worked example. In Claude Code, `/path .` runs the same command.

Anyone who has done product ownership or project management will recognize the tasks as issues: a title, an estimate, what they depend on, and what they close. A few commands keep a durable record of where the system stands and what has to change next, without spending a session's context re-establishing it.

## Commands

```bash
path .                       # initialize or refresh a project, then build its graph
path status                  # where the backlog stands; run from a parent directory for a portfolio
path next [--batch]          # the next task to start, without reading every task file
path check [T-NNN|B-NNN]     # proof of done: validate a task, a batch, or the whole project
path metrics [--json]        # burn-up, rate and forecast, volatility, decision latency, drift
path new task "<title>" --effort N [--batch B-NNN]
path new batch "<title>"
path new retrospective --for T-NNN|B-NNN
path task start|block|complete T-NNN
path batch add|remove|order|start|complete B-NNN [T-NNN ...]
path log change|drift|issue T-NNN "<note>"
path decision raise|resolve|list
path close                   # session-close entry, then regenerate status.html
path migrate [--apply]       # convert a legacy work-order project to OKF tasks
```

## Project Structure

```
/my-project/
  AGENTS.md                  # entry point for any agent; CLAUDE.md is a pointer to it
  .path/
    requirements/            # 01-overview, 02-user-stories, 03-functional, 04-non-functional
    blueprints/              # 01-architecture, 02-folder-structure, 03-conventions, ...
    tasks/
      index.md               # OKF directory listing (no frontmatter — the spec forbids it)
      TASK-TEMPLATE.md
      T-001-[slug].md        # one file per task
    build-log/               # one file per decision, problem, or session close
    decisions-log.md         # only if a decision has actually been raised
    status.html              # burn-up, volatility, decision latency, drift — regenerated
```

This repository is self-hosted: it is a Path project with its documents at the top level rather than nested under `.path/`, since `.path/.path/` would be its own kind of joke.

## Migrating an Existing Project

Projects using the older work-order format convert with one command:

```bash
cd ~/code/my-project
path migrate                 # dry run: reports everything, changes nothing
path migrate --apply         # requires a clean git tree
path check                   # verify
```

Migration renames `WO-NNN` to `T-NNN`, lifts header fields and log sections into frontmatter, rewrites links, converts `CLAUDE.md` to `AGENTS.md`, and removes the per-project script copies. Anything ambiguous is reported rather than guessed.

To undo: `git reset --hard HEAD && git clean -fd`. **Not** `git checkout .` — the renames are staged, so it would restore almost nothing.

## Working with AI Agents

Point your agent at `AGENTS.md`. It will find everything from there.

Tasks are designed to be self-contained: an agent should be able to execute one from a cold start, reading only `AGENTS.md`, the task, and the requirements and blueprints it links to. The Definition of Ready reduces ambiguity before work starts; the Definition of Done and `path check` prevent an incomplete handoff.

## License

MIT
