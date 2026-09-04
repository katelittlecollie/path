"""Initialize a new Path project, or self-heal an existing one.

This is the non-graphify half of `path .`; the graph-building half lives in
graphify_run.py. Splitting them keeps each half testable without the other,
and keeps the graph — which is optional and can fail for reasons that have
nothing to do with documentation — from being tangled up with the part that
must not fail.

Refreshing an existing project used to mean comparing local copies of the
scripts and templates against the canonical repository and raising a task for
any drift found. That entire mechanism is gone, and deliberately so — see
blueprints/01-architecture.md's "consumer project contains no Path code."
There is one copy of the tool, on `$PATH`, so there is nothing left to drift
from. What remains for a refresh is much smaller: make sure the handful of
files a project keeps its own copy of on purpose (F-18's task template, the
OKF index files) actually exist.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import okf

CANONICAL_ROOT = Path(__file__).resolve().parent.parent  # the Path repo itself


def _stub(doc_type: str, title: str, sections: list[str]) -> str:
    body = "\n\n".join(f"## {s}\n\n[Fill this in.]" for s in sections)
    return (
        f"---\ntype: {doc_type}\ntitle: {title}\ndescription: \ntags: []\n"
        f"timestamp: {date.today().isoformat()}T00:00:00Z\n---\n\n# {title}\n\n{body}\n"
    )


REQUIREMENT_STUBS = {
    "01-overview.md": lambda: _stub("Requirement", "Overview", ["What this is", "Why it exists"]),
    "02-user-stories.md": lambda: _stub("Requirement", "User Stories", ["Who uses this, and how"]),
    "03-functional.md": lambda: _stub("Requirement", "Functional Requirements", ["F-01"]),
    "04-non-functional.md": lambda: _stub(
        "Requirement", "Non-Functional Requirements", ["NF-01"]
    ),
}

BLUEPRINT_STUBS = {
    "01-architecture.md": lambda: _stub(
        "Blueprint", "Architecture", ["System design", "Key decisions"]
    ),
    "02-folder-structure.md": lambda: _stub("Blueprint", "Folder Structure", ["Layout"]),
}


def _agents_template(project_name: str) -> str:
    today = date.today().isoformat()
    return f"""# {project_name} — AI Navigation Guide

[Fill this in: what does {project_name} do, and why?]

## How to Navigate This Project

| Need | Location |
|------|----------|
| What it does and why | `.path/requirements/01-overview.md` |
| Who uses it and how | `.path/requirements/02-user-stories.md` |
| Functional requirements | `.path/requirements/03-functional.md` |
| Non-functional requirements | `.path/requirements/04-non-functional.md` |
| System architecture | `.path/blueprints/01-architecture.md` |
| Folder structure | `.path/blueprints/02-folder-structure.md` |
| Document conventions | see the Path repository's `blueprints/03-conventions.md` |
| Task template | `.path/tasks/TASK-TEMPLATE.md` |
| Decision and build history | `.path/build-log/` |

## Executing a Task

1. Read this file first for orientation.
2. Read the referenced task in `.path/tasks/`.
3. Follow the Context links in the task to read the relevant requirements and blueprints.
4. Complete every item in the task's task list.
5. Verify all acceptance criteria before marking complete.
6. Write a `RETROSPECTIVE` build log entry, and update this file. The entry must declare the task in its `path.related_tasks` frontmatter — `path check` reads that field, not the prose.
7. Run `path check T-NNN` — it verifies the completion claim mechanically.

## Available Commands

Path is a single command on `$PATH`. This project contains no Path code.

```bash
path status                  # project status and task queue
path check [T-NNN]           # proof of done: validate a task, or the whole project
path metrics                 # burn-up, volatility, drift — read from frontmatter
path new task "<title>" --effort N
path task start|block|complete T-NNN
path log change|drift|issue T-NNN "<note>"
path close                   # session-close entry, then regenerate status.html
```

## Current Task

None assigned. See `.path/tasks/` for available tasks.

## Project Status

**Phase:** Initial documentation
**Last updated:** {today}

## Global Profile

If `$LCP_HOME` is set, read `$LCP_HOME/profile/index.md` (or run `path profile`) for the
project owner's working preferences. **Anything in this repository overrides it.**

Standing order: when you learn something true of the project owner, not this project —
a working preference, a stack default, a personal convention — persist it immediately
with `path profile add <doc> "<text>"` (`doc`: identity, working-style, conventions, or
stack). Never hand-edit the profile files.
"""


def is_initialized(start: Path) -> bool:
    return okf.find_project_root(start) is not None


def init_project(cwd: Path) -> tuple[Path, list[Path]]:
    """Scaffold `.path/` under `cwd`, plus `AGENTS.md` at the project root.

    Returns (root, created) — root is the new `.path/` directory (the return
    value `okf.find_project_root` would give from now on), and created lists
    every file written, for the caller to report. Dotted deliberately: a
    hidden directory reads as tooling, matching `.git`/`.github`/`.vscode`,
    and can never collide with a project's own source tree wanting to use the
    plain name `path`.
    """
    root = cwd / ".path"
    created: list[Path] = []

    for directory in ("requirements", "blueprints", "tasks", "build-log"):
        (root / directory).mkdir(parents=True, exist_ok=True)

    for name, factory in REQUIREMENT_STUBS.items():
        path = root / "requirements" / name
        path.write_text(factory(), encoding="utf-8")
        created.append(path)

    for name, factory in BLUEPRINT_STUBS.items():
        path = root / "blueprints" / name
        path.write_text(factory(), encoding="utf-8")
        created.append(path)

    template_dest = root / "tasks" / "TASK-TEMPLATE.md"
    template_dest.write_text(
        (CANONICAL_ROOT / "tasks" / "TASK-TEMPLATE.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    created.append(template_dest)

    # Both indexes go through the same rebuild the rest of the CLI uses, so a
    # freshly scaffolded project and a long-lived one cannot end up describing
    # themselves in two different shapes. A new project has no tasks and no
    # entries yet, so both come out empty — correctly so.
    okf.rebuild_tasks_index(root / "tasks", cwd.name)
    created.append(root / "tasks" / "index.md")

    okf.rebuild_build_log_index(root / "build-log", cwd.name)
    created.append(root / "build-log" / "index.md")

    # decisions-log.md is deliberately not created here. `path check` treats it
    # as optional — it only validates one if it finds one — and decisions.py's
    # own load() already creates it lazily the moment `path decision raise`
    # actually needs it. Scaffolding it eagerly would mean a plain project that
    # never has a question to raise carries a permanently-empty file for no
    # reason other than this function having run once.

    agents_path = cwd / "AGENTS.md"
    if not agents_path.is_file():
        agents_path.write_text(_agents_template(cwd.name), encoding="utf-8")
        created.append(agents_path)

    return root, created


def refresh_project(root: Path) -> list[str]:
    """Self-heal the small set of files a project keeps its own copy of.
    Returns what was healed; empty means nothing needed it."""
    healed: list[str] = []
    project = okf.project_dir(root)

    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    template = tasks_dir / "TASK-TEMPLATE.md"
    if not template.is_file():
        template.write_text(
            (CANONICAL_ROOT / "tasks" / "TASK-TEMPLATE.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        healed.append(str(template.relative_to(project)))

    # Rebuilt unconditionally, not only when missing. An index that exists but
    # is stale is the common case and the damaging one: it reads as
    # authoritative, `path check` has no claim in it to validate, and the
    # absence-only heal that used to live here never touched it. Rebuilding
    # every refresh makes `path .` the thing that repairs the drift.
    before = (tasks_dir / "index.md").read_text(encoding="utf-8") if (tasks_dir / "index.md").is_file() else None
    okf.rebuild_tasks_index(tasks_dir, project.name)
    if (tasks_dir / "index.md").read_text(encoding="utf-8") != before:
        healed.append(str((tasks_dir / "index.md").relative_to(project)))

    build_log = root / "build-log"
    if build_log.is_dir():
        before = (build_log / "index.md").read_text(encoding="utf-8") if (build_log / "index.md").is_file() else None
        okf.rebuild_build_log_index(build_log, project.name)
        if (build_log / "index.md").read_text(encoding="utf-8") != before:
            healed.append(str((build_log / "index.md").relative_to(project)))

    # decisions-log.md is not healed here, on purpose — see init_project's
    # comment. Its absence is not damage: most projects that predate this
    # tooling never had one and never needed one, and `path .` running on such
    # a project must not be the thing that gives it a new tracked file it
    # never asked for. It is created the moment `path decision raise` is
    # actually used.

    if not (project / "AGENTS.md").is_file():
        (project / "AGENTS.md").write_text(_agents_template(project.name), encoding="utf-8")
        healed.append("AGENTS.md")

    return healed
