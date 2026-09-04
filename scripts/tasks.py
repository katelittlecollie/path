"""Task lifecycle: create, transition, log.

Implements F-35 through F-37. Everything here is deterministic — an identifier
is next or it is wrong, a transition is legal or it is not, a date is today or
it is a fiction. None of it benefits from an executor's judgment, which is
exactly why it lives in code rather than in an instruction an agent is trusted
to follow. See blueprints/01-architecture.md.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import okf

TASK_ID_RE = re.compile(r"\AT-(\d{3,})\Z")

# The scale is the Fibonacci sequence, and the sequence does not stop. The
# points documented in blueprints/03-conventions.md go up to 21 because that is
# as far as the described meanings usefully go, but a task larger than that gets
# 34, and the honest answer to "how big is this" is never "the largest number my
# tooling accepts". A ceiling would quietly compress everything above it into
# one bucket and make the biggest pieces of work indistinguishable.
FIBONACCI_EFFORT = (1, 2, 3, 5, 8, 13, 21, 34, 55, 89)


def is_fibonacci(value) -> bool:
    """True for any Fibonacci number. There is no upper bound."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        return False
    previous, current = 1, 1
    while current < value:
        previous, current = current, previous + current
    return current == value

# A transition is legal or it is not. Two rules are worth stating out loud:
# a task cannot be completed without having been started (otherwise "in
# progress" means nothing and the burn-up has no interval to measure), and a
# completed task can be reopened, because bugs are found after the fact and
# pretending otherwise would just push people into editing YAML by hand.
TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in-progress", "blocked"},
    "in-progress": {"complete", "blocked", "pending"},
    "blocked": {"in-progress", "pending"},
    "complete": {"in-progress"},
}

LOG_KINDS = ("change", "drift", "issue")
DRIFT_KINDS = ("correction", "retry", "post-completion-bug")


class TaskError(Exception):
    """Something the caller asked for is not allowed."""


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        raise TaskError(f"title {title!r} produces an empty slug; give it some letters")
    return slug


def tasks_dir(root: Path) -> Path:
    return root / "tasks"


def task_paths(root: Path) -> list[Path]:
    return id_paths(root, "T")


def find_task(root: Path, task_id: str) -> Path:
    matches = [p for p in task_paths(root) if p.name.startswith(f"{task_id}-")]
    if not matches:
        raise TaskError(f"no task {task_id} in {tasks_dir(root)}")
    if len(matches) > 1:
        raise TaskError(f"{task_id} matches more than one file: {', '.join(p.name for p in matches)}")
    return matches[0]


def next_id(root: Path, prefix: str = "T") -> str:
    """Allocate the next identifier. Sequential, and never reused (F-36).

    The maximum ever *referred to* wins, not the count and not the first gap.
    Existing files are not enough on their own: deleting T-002 would free the
    number, and handing it to the next task would leave the build log's history
    describing two different pieces of work by one id. The log is the one thing
    that has to stay trustworthy, so the search covers everything that could
    hold a reference.

    The residual case is a task deleted before anything ever mentioned it. Its
    number can be reused, and that is harmless precisely because nothing points
    at it — there is no history to make ambiguous.

    Batches (`B-NNN`) allocate from their own sequence through the same search
    rather than a second copy of it, because the rule they need is identical:
    an id the build log has already described must never come back meaning
    something else.
    """
    highest = 0
    filename_re = re.compile(rf"\A{prefix}-(\d{{3,}})-[a-z0-9-]+\.md\Z")
    for path in id_paths(root, prefix):
        match = filename_re.match(path.name)
        if match:
            highest = max(highest, int(match.group(1)))

    for referenced in _referenced_ids(root, prefix):
        highest = max(highest, referenced)

    return f"{prefix}-{highest + 1:03d}"


def id_paths(root: Path, prefix: str) -> list[Path]:
    directory = tasks_dir(root)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob(f"{prefix}-*.md") if not okf.is_reserved(p))


def _referenced_ids(root: Path, prefix: str = "T") -> set[int]:
    """Every X-NNN mentioned anywhere a reference could survive a deleted file."""
    found: set[int] = set()
    candidates: list[Path] = []

    for directory in ("build-log", "strategy", "requirements", "blueprints", "tasks"):
        target = root / directory
        if target.is_dir():
            # Reserved index files are excluded on purpose. An index is derived
            # from the directory it sits in, so every id it names also appears
            # in a file this loop already reads — it can never be the sole
            # surviving reference to anything. Counting it would make id
            # allocation depend on a regenerated cache: an index rebuilt while
            # a task still existed would keep reserving that number after the
            # file was deleted, which is precisely the residual case F-36
            # allows to be reused.
            candidates.extend(p for p in target.glob("*.md") if not okf.is_reserved(p))

    for extra in (root / "decisions-log.md", root / "AGENTS.md", root.parent / "AGENTS.md"):
        if extra.is_file():
            candidates.append(extra)

    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        found.update(int(n) for n in re.findall(rf"\b{prefix}-(\d{{3,}})\b", text))
    return found


def _template(root: Path) -> okf.Doc:
    """The project's template, or the canonical one shipped with Path (F-18)."""
    local = tasks_dir(root) / "TASK-TEMPLATE.md"
    if local.is_file():
        return okf.load(local)
    canonical = Path(__file__).resolve().parent.parent / "tasks" / "TASK-TEMPLATE.md"
    if canonical.is_file():
        return okf.load(canonical)
    raise TaskError(f"no TASK-TEMPLATE.md in {tasks_dir(root)} or in the Path install")


def rebuild_index(root: Path) -> list[str]:
    """Refresh `tasks/index.md` to match the frontmatter on disk.

    Called from every function that changes what the index should say. The
    index is a derived artefact; nothing should ever have to remember to
    update it by hand, because for a long time nothing did.
    """
    return okf.rebuild_tasks_index(
        tasks_dir(root), okf.project_dir(root).name
    )


def new_task(
    root: Path,
    title: str,
    effort: int | None = None,
    project: str | None = None,
    drafted_by: str = "Human",
    implements: list[str] | None = None,
    requires: list[str] | None = None,
) -> Path:
    if effort is not None and not is_fibonacci(effort):
        raise TaskError(
            f"effort must be a Fibonacci number (1, 2, 3, 5, 8, 13, 21, ...), got {effort}"
        )

    for prerequisite in requires or []:
        if not TASK_ID_RE.match(prerequisite):
            raise TaskError(f"--requires {prerequisite!r} is not a task id")
        find_task(root, prerequisite)  # raises if it does not exist

    task_id = next_id(root)
    doc = _template(root)
    doc.path = tasks_dir(root) / f"{task_id}-{slugify(title)}.md"
    if doc.path.exists():
        raise TaskError(f"{doc.path} already exists")

    doc.meta["title"] = title
    doc.meta["description"] = ""
    doc.meta["tags"] = []
    doc.meta["timestamp"] = _now()

    meta = doc.path_meta
    meta["id"] = task_id
    meta["status"] = "pending"
    meta["batch"] = None
    meta["effort"] = effort
    meta["created"] = _today()
    meta["updated"] = _today()
    meta["completed"] = None
    meta["project"] = project or okf.project_dir(root).name
    meta["drafted_by"] = drafted_by
    meta["completed_by"] = []
    meta["requires"] = requires or []
    meta["implements"] = implements or []
    meta["change_log"] = []
    meta["drift_log"] = []
    meta["issues"] = []
    meta["proof"] = {"checked_at": None, "result": None}

    doc.body = doc.body.replace("[Short Descriptive Title]", title)

    tasks_dir(root).mkdir(parents=True, exist_ok=True)
    okf.save(doc)
    rebuild_index(root)
    return doc.path


def transition(root: Path, task_id: str, to_status: str, by: str | None = None) -> tuple[Path, str]:
    """Move a task to a new status. Returns (path, previous_status)."""
    path = find_task(root, task_id)
    doc = okf.load(path)
    meta = doc.path_meta
    current = meta.get("status")

    if current == to_status:
        raise TaskError(f"{task_id} is already {to_status}")
    if current not in TRANSITIONS:
        raise TaskError(f"{task_id} has an unrecognised status {current!r}; fix it by hand")
    if to_status not in TRANSITIONS[current]:
        legal = ", ".join(sorted(TRANSITIONS[current])) or "nothing"
        raise TaskError(
            f"{task_id} is {current!r}; it cannot become {to_status!r}. Legal from here: {legal}."
        )

    meta["status"] = to_status
    meta["updated"] = _today()
    doc.meta["timestamp"] = _now()

    # The iff that keeps the burn-up honest, maintained here so no one has to
    # remember it: completing stamps the date, reopening clears it.
    if to_status == "complete":
        meta["completed"] = _today()
        if by:
            completed_by = meta.setdefault("completed_by", [])
            if by not in completed_by:
                completed_by.append(by)
    elif current == "complete":
        meta["completed"] = None

    okf.save(doc)
    rebuild_index(root)
    return path, current


def log(
    root: Path,
    kind: str,
    task_id: str,
    note: str,
    resolution: str | None = None,
    drift_kind: str | None = None,
    effort_to_correct: int | None = None,
) -> Path:
    """Append a structured entry to a task's frontmatter."""
    if kind not in LOG_KINDS:
        raise TaskError(f"log kind must be one of {', '.join(LOG_KINDS)}, got {kind!r}")

    path = find_task(root, task_id)
    doc = okf.load(path)
    meta = doc.path_meta

    if kind == "change":
        # status_at_change is captured rather than asked for. The volatility
        # chart classifies impact from it, and a value supplied after the fact
        # would be a guess at best.
        entry = {
            "date": _today(),
            "status_at_change": meta.get("status"),
            "note": note,
        }
        meta.setdefault("change_log", []).append(entry)

    elif kind == "drift":
        if drift_kind not in DRIFT_KINDS:
            raise TaskError(f"--kind must be one of {', '.join(DRIFT_KINDS)}, got {drift_kind!r}")
        if effort_to_correct not in (1, 2, 3):
            raise TaskError(f"--effort must be 1, 2, or 3, got {effort_to_correct!r}")
        entry = {
            "date": _today(),
            "kind": drift_kind,
            "effort_to_correct": effort_to_correct,
            "note": note,
        }
        meta.setdefault("drift_log", []).append(entry)

    else:  # issue
        entry = {"date": _today(), "note": note, "resolution": resolution}
        meta.setdefault("issues", []).append(entry)

    meta["updated"] = _today()
    doc.meta["timestamp"] = _now()
    okf.save(doc)
    return path


def summary(root: Path) -> list[dict]:
    """Every task's frontmatter, for status and metrics."""
    rows = []
    for path in task_paths(root):
        try:
            doc = okf.load(path)
            meta = dict(doc.path_meta)
        except okf.OKFError:
            continue
        meta["_path"] = path
        meta["_relpath"] = path.relative_to(root) if path.is_relative_to(root) else path
        meta["_title"] = doc.meta.get("title") or ""
        rows.append(meta)
    return rows
