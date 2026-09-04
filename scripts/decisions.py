"""The decisions log: raise a question, resolve it, read the ages.

Implements F-31. Rows live in `decisions-log.md`'s frontmatter; the body keeps
the preamble explaining why the file tracks Decisions and not a full RAID log.

Age is computed here and stored nowhere. The previous version of this file kept
an `Age (days)` column that the status page ignored and recomputed — a number
that began going stale the moment it was written, sitting next to the two dates
it was derived from. See blueprints/06-okf-mapping.md.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import okf

PREAMBLE = """
Tracks open questions raised to the project owner that a task can't proceed past — the moment the Definition of Ready's Ambiguity Check says "raise it as a question before proceeding," it gets a row here.

This deliberately covers only Decisions, not a full RAID log. Risks already live in a task's `blocked` status, Assumptions belong inline in the relevant blueprint, Issues live in each task's `path.issues`, and Dependencies live in each task's `path.requires` — duplicating those here would just create a second place to keep in sync.

Raise a row the moment a question is surfaced with `path decision raise`, and answer it with `path decision resolve`. Age is computed from `raised` and `resolved` whenever something asks; it is never stored.
"""


class DecisionError(Exception):
    """Something the caller asked for is not allowed."""


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_path(root: Path) -> Path:
    return root / "decisions-log.md"


def load(root: Path) -> okf.Doc:
    """Read the decisions log, creating it in memory if it does not exist yet."""
    path = log_path(root)
    if path.is_file():
        return okf.load(path)
    return okf.Doc(
        path=path,
        meta={
            "type": "Decision Log",
            "title": f"{okf.project_dir(root).name} — Decisions Log",
            "description": "Open questions raised to the project owner that a task cannot proceed past.",
            "tags": ["decisions"],
            "timestamp": _now(),
            "path": {"decisions": []},
        },
        body=f"\n# Decisions Log\n{PREAMBLE}",
    )


def rows(doc: okf.Doc) -> list[dict]:
    decisions = doc.path_meta.setdefault("decisions", [])
    if decisions is None:
        decisions = doc.path_meta["decisions"] = []
    if not isinstance(decisions, list):
        raise DecisionError(f"{doc.path}: path.decisions must be a list")
    return decisions


def raise_decision(root: Path, question: str, related_task: str | None = None) -> int:
    """Add a row. Returns its 1-based number, which is what `resolve` takes."""
    if not question.strip():
        raise DecisionError("a decision needs a question")

    doc = load(root)
    entries = rows(doc)
    entries.append(
        {
            "question": question.strip(),
            "related_task": related_task,
            "raised": _today(),
            "resolved": None,
            "answer": None,
        }
    )
    doc.meta["timestamp"] = _now()
    okf.save(doc)
    return len(entries)


def resolve_decision(root: Path, number: int, answer: str) -> dict:
    if not answer.strip():
        raise DecisionError("resolving a decision needs an answer")

    doc = load(root)
    entries = rows(doc)
    if not 1 <= number <= len(entries):
        raise DecisionError(
            f"no decision {number}; the log has {len(entries)} "
            f"{'row' if len(entries) == 1 else 'rows'}"
        )

    entry = entries[number - 1]
    if entry.get("resolved"):
        raise DecisionError(
            f"decision {number} was already resolved on {entry['resolved']}: {entry.get('answer')!r}"
        )

    entry["resolved"] = _today()
    entry["answer"] = answer.strip()
    doc.meta["timestamp"] = _now()
    okf.save(doc)
    return entry


def age_days(entry: dict, today: date | None = None) -> int | None:
    """Days from raised to resolved, or to today while still open."""
    raised = entry.get("raised")
    if not raised:
        return None
    try:
        start = datetime.strptime(str(raised), "%Y-%m-%d").date()
    except ValueError:
        return None

    end_value = entry.get("resolved")
    if end_value:
        try:
            end = datetime.strptime(str(end_value), "%Y-%m-%d").date()
        except ValueError:
            return None
    else:
        end = today or date.today()
    return (end - start).days


def listing(root: Path, open_only: bool = False) -> list[dict]:
    """Every row, numbered, with age computed at read time.

    A log that is missing, or still in the pre-OKF table format, yields nothing
    rather than raising: reporting is not validation. `path check` is what says
    a document does not conform, and it says so about every file at once. A
    metrics command that dies on the first unmigrated file would just be a worse
    validator that also refuses to do its own job.
    """
    path = log_path(root)
    if not path.is_file():
        return []
    try:
        doc = okf.load(path)
    except okf.OKFError:
        return []
    result = []
    for index, entry in enumerate(rows(doc), start=1):
        if open_only and entry.get("resolved"):
            continue
        row = dict(entry)
        row["number"] = index
        row["age_days"] = age_days(entry)
        result.append(row)
    return result
