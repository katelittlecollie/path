"""Batches: a set of tasks executed, and accounted for, as one unit.

Implements F-53 and F-54. A batch exists to make the bookkeeping proportional
to the work. Completing a task requires a retrospective naming it, a validation
run, and a pass through the Definition of Done; on a one-point task that
ceremony is most of the cost, and paying it four times for four small tasks
buys nothing the first payment did not already buy. A batch pays it once.

Two things are deliberately not stored here.

A batch has no `status` field. Its status is a fact about its members, and
`derived_status` computes it on read. Writing it to disk would create a second
copy of something already recorded, which is the same argument F-31 uses to
forbid storing a decision's age — and the same failure, since the copy is only
correct until the moment a member moves.

A batch has no `completed` date either. It is the latest completion among its
members, and for the same reason it is computed rather than kept.

What the batch *does* own is the intended order, at `path.sequence`. Membership
is owned by the task, at `path.batch`. That does put the member set in two
places, so `path check` fails a batch whose sequence and membership disagree,
and both are written by the commands here rather than by hand. The drift is not
discouraged; it is uncommittable.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import next as next_mod
import okf
import tasks as tasks_mod
from tasks import TaskError

BATCH_ID_RE = re.compile(r"\AB-(\d{3,})\Z")
BATCH_FILENAME_RE = re.compile(r"\AB-(\d{3,})-[a-z0-9-]+\.md\Z")

def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def batch_paths(root: Path) -> list[Path]:
    return tasks_mod.id_paths(root, "B")


def find_batch(root: Path, batch_id: str) -> Path:
    matches = [p for p in batch_paths(root) if p.name.startswith(f"{batch_id}-")]
    if not matches:
        raise TaskError(f"no batch {batch_id} in {tasks_mod.tasks_dir(root)}")
    if len(matches) > 1:
        raise TaskError(
            f"{batch_id} matches more than one file: {', '.join(p.name for p in matches)}"
        )
    return matches[0]


def _template(root: Path) -> okf.Doc:
    """The project's batch template, or the canonical one shipped with Path."""
    local = tasks_mod.tasks_dir(root) / "BATCH-TEMPLATE.md"
    if local.is_file():
        return okf.load(local)
    canonical = Path(__file__).resolve().parent.parent / "tasks" / "BATCH-TEMPLATE.md"
    if canonical.is_file():
        return okf.load(canonical)
    raise TaskError(
        f"no BATCH-TEMPLATE.md in {tasks_mod.tasks_dir(root)} or in the Path install"
    )


def summary(root: Path) -> list[dict]:
    """Every batch's frontmatter, for status, metrics, and the index."""
    rows = []
    for path in batch_paths(root):
        try:
            doc = okf.load(path)
            meta = dict(doc.path_meta)
        except okf.OKFError:
            continue
        meta["_path"] = path
        meta["_title"] = doc.meta.get("title") or path.stem
        rows.append(meta)
    return rows


def rollups(root: Path, task_rows: list[dict] | None = None) -> list[dict]:
    rows = tasks_mod.summary(root) if task_rows is None else task_rows
    return [next_mod.rollup(rows, batch) for batch in summary(root)]


def new_batch(
    root: Path,
    title: str,
    project: str | None = None,
    drafted_by: str = "Human",
) -> Path:
    batch_id = tasks_mod.next_id(root, "B")
    doc = _template(root)
    doc.path = tasks_mod.tasks_dir(root) / f"{batch_id}-{tasks_mod.slugify(title)}.md"
    if doc.path.exists():
        raise TaskError(f"{doc.path} already exists")

    doc.meta["title"] = title
    doc.meta["description"] = ""
    doc.meta["tags"] = []
    doc.meta["timestamp"] = _now()

    meta = doc.path_meta
    meta["id"] = batch_id
    meta["created"] = _today()
    meta["updated"] = _today()
    meta["project"] = project or okf.project_dir(root).name
    meta["drafted_by"] = drafted_by
    meta["sequence"] = []

    doc.body = doc.body.replace("[Short Descriptive Title]", title)

    tasks_mod.tasks_dir(root).mkdir(parents=True, exist_ok=True)
    okf.save(doc)
    tasks_mod.rebuild_index(root)
    return doc.path


def _write_sequence(root: Path, batch_id: str, sequence: list[str]) -> Path:
    path = find_batch(root, batch_id)
    doc = okf.load(path)
    doc.path_meta["sequence"] = sequence
    doc.path_meta["updated"] = _today()
    doc.meta["timestamp"] = _now()
    okf.save(doc)
    return path


def _set_task_batch(root: Path, task_id: str, batch_id: str | None) -> None:
    path = tasks_mod.find_task(root, task_id)
    doc = okf.load(path)
    doc.path_meta["batch"] = batch_id
    doc.path_meta["updated"] = _today()
    doc.meta["timestamp"] = _now()
    okf.save(doc)


def add(root: Path, batch_id: str, task_ids: list[str]) -> Path:
    """Put tasks in a batch: membership on the task, order on the batch."""
    find_batch(root, batch_id)
    for task_id in task_ids:
        if not tasks_mod.TASK_ID_RE.match(task_id):
            raise TaskError(f"{task_id!r} is not a task id")
        path = tasks_mod.find_task(root, task_id)
        current = okf.load(path).path_meta.get("batch")
        if current and str(current) != batch_id:
            raise TaskError(
                f"{task_id} already belongs to {current}; "
                f"remove it from there before adding it to {batch_id}"
            )

    sequence = list(okf.load(find_batch(root, batch_id)).path_meta.get("sequence") or [])
    for task_id in task_ids:
        _set_task_batch(root, task_id, batch_id)
        if task_id not in sequence:
            sequence.append(task_id)

    path = _write_sequence(root, batch_id, sequence)
    tasks_mod.rebuild_index(root)
    return path


def remove(root: Path, batch_id: str, task_ids: list[str]) -> Path:
    find_batch(root, batch_id)
    sequence = list(okf.load(find_batch(root, batch_id)).path_meta.get("sequence") or [])
    for task_id in task_ids:
        if task_id not in sequence:
            raise TaskError(f"{task_id} is not in {batch_id}")
        sequence.remove(task_id)
        _set_task_batch(root, task_id, None)

    path = _write_sequence(root, batch_id, sequence)
    tasks_mod.rebuild_index(root)
    return path


def member_ids(root: Path, batch_id: str) -> list[str]:
    """The batch's members, in its own order. Raises if the batch is unknown."""
    batch_meta = okf.load(find_batch(root, batch_id)).path_meta
    rows = tasks_mod.summary(root)
    return [str(r.get("id")) for r in next_mod.members(rows, batch_id, batch_meta.get("sequence") or [])]


def start(root: Path, batch_id: str) -> list[tuple[str, str]]:
    """Move every pending member to in-progress. Returns what changed.

    Members already in progress are left alone rather than treated as an error.
    Starting a batch you are halfway through is the ordinary case, not a mistake.
    """
    moved = []
    for task_id in member_ids(root, batch_id):
        path = tasks_mod.find_task(root, task_id)
        if okf.load(path).path_meta.get("status") != "pending":
            continue
        tasks_mod.transition(root, task_id, "in-progress")
        moved.append((task_id, "in-progress"))
    return moved


def complete(root: Path, batch_id: str, by: str | None = None) -> list[tuple[str, str]]:
    """Complete every in-progress member, or refuse and change nothing.

    The refusal is the point. A batch command that quietly completed a pending
    member would make "in progress" mean nothing and leave the burn-up with no
    interval to measure — which is the whole reason `TRANSITIONS` refuses that
    move one task at a time. Reducing ceremony is the goal here; reducing rigour
    is not, so every rule still applies, it just applies once.

    Every member is inspected before any is written, so a batch that cannot be
    completed is not left half-completed.
    """
    ids = member_ids(root, batch_id)
    if not ids:
        raise TaskError(f"{batch_id} has no members; nothing to complete")

    pending = []
    for task_id in ids:
        status = okf.load(tasks_mod.find_task(root, task_id)).path_meta.get("status")
        if status not in ("in-progress", "complete"):
            pending.append(f"{task_id} is {status!r}")

    if pending:
        raise TaskError(
            f"{batch_id} cannot be completed: {'; '.join(pending)}. "
            f"Start them first with `path batch start {batch_id}`."
        )

    moved = []
    for task_id in ids:
        if okf.load(tasks_mod.find_task(root, task_id)).path_meta.get("status") == "complete":
            continue
        tasks_mod.transition(root, task_id, "complete", by=by)
        moved.append((task_id, "complete"))
    return moved


def order(root: Path, batch_id: str, task_ids: list[str]) -> Path:
    """Rewrite the execution order. Refuses an ordering that is not a permutation.

    An order that omitted a member would silently drop it out of every view
    built from the sequence, and one that invented a member would put a task in
    a batch without ever touching the task. Both are the disagreement
    `check_batch` exists to catch, so neither is allowed in through the front
    door.
    """
    find_batch(root, batch_id)
    rows = tasks_mod.summary(root)
    actual = {str(r.get("id")) for r in rows if str(r.get("batch") or "") == batch_id}
    given = [str(t) for t in task_ids]

    duplicates = sorted({t for t in given if given.count(t) > 1})
    if duplicates:
        raise TaskError(f"{batch_id} ordering names {', '.join(duplicates)} more than once")

    missing = sorted(actual - set(given))
    if missing:
        raise TaskError(
            f"{batch_id} ordering omits {', '.join(missing)}; "
            "an order must name every member of the batch"
        )
    extra = sorted(set(given) - actual)
    if extra:
        raise TaskError(
            f"{batch_id} ordering names {', '.join(extra)}, which is not in the batch; "
            f"add it with `path batch add {batch_id} {extra[0]}` first"
        )

    path = _write_sequence(root, batch_id, given)
    tasks_mod.rebuild_index(root)
    return path
