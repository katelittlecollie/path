"""Build log entries the tooling writes.

Right now that is one thing: a `RETROSPECTIVE` scaffold. It exists because the
retrospective is the only artefact the completion process requires and no
command produced, so every one of them was hand-built — including the field
`path check` actually reads.

That gap had a cost with a name. T-030 fixed a checker that matched a task id
anywhere in an entry's prose, which let a task pass on a name-drop: it was
checked off against a retrospective that mentioned it only to say it was *not*
covered there. The fix made the checker read `path.related_tasks`, and this is
the other half of that fix — a command that fills the field in, so the list is
never a thing someone has to remember to write correctly.

The division of labour is Path's usual one. Which tasks an entry closes is a
fact, and it is filled in here. What was learned is judgment, and this leaves
prompts for a person or an agent to answer.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import okf
from tasks import TaskError

RETROSPECTIVE_PROMPTS = """## What Was Built

Name what is true now that was not true before. Not a list of files changed —
`git log` already has that.

## What Went Wrong

The corrections, the retries, the things that took longer than the estimate said
they would. This section is the reason the entry is worth writing; an entry with
nothing here is usually an entry nobody thought hard about.

## What the Estimate Missed

Where the effort points and the actual difficulty diverged, and what the next
estimate should learn from it. Do not revise the original estimate to match the
outcome — a scale corrected after the fact measures nothing.

## What Changed in the Documents

Requirements, blueprints, or conventions this work altered, and why. If it
revealed a gap that let a defect through, say which document should have caught
it.
"""


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def entry_path(root: Path, slug: str) -> Path:
    """A dated filename, suffixed rather than overwritten on a same-day repeat."""
    build_log = root / "build-log"
    build_log.mkdir(parents=True, exist_ok=True)
    base = f"{_today()}-{slug}"
    candidate = build_log / f"{base}.md"
    n = 2
    while candidate.is_file():
        candidate = build_log / f"{base}-{n}.md"
        n += 1
    return candidate


def write_retrospective(root: Path, related_tasks: list[str], title: str, tags=None) -> Path:
    """Scaffold a RETROSPECTIVE with `path.related_tasks` already filled in."""
    if not related_tasks:
        raise TaskError("a retrospective must name at least one task")

    slug = _slugify(title) or "retrospective"
    path = entry_path(root, slug)
    doc = okf.Doc(
        path=path,
        meta={
            "type": "Build Log Entry",
            "title": f"{_today()} — {title} — Retrospective",
            "description": "",
            "tags": list(tags or []),
            "timestamp": _now(),
            "path": {
                "date": _today(),
                "entry_type": "RETROSPECTIVE",
                "related_tasks": list(related_tasks),
            },
        },
        body=(
            f"\n# {title} — Retrospective\n\n"
            f"Closes {', '.join(related_tasks)}.\n\n"
            f"{RETROSPECTIVE_PROMPTS}"
        ),
    )
    okf.save(doc)
    okf.rebuild_build_log_index(root / "build-log", okf.project_dir(root).name)
    return path
