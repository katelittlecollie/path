"""Derived views of a backlog: readiness, ranking, and batch progress.

Everything here is a pure function of a list of frontmatter rows. Nothing reads
a file or knows what a project directory looks like, which is what lets the four
surfaces that answer "what is next" — `path next`, `path status`, `tasks/index.md`,
and `status.html` — share one computation instead of each growing its own sort.
Two of them disagreeing would be worse than either alone.

What to work on next, computed rather than guessed.

Implements F-58. A task is ready when it is pending and every task it names in
`path.requires` is complete. That is not a new fact about anything — it is two
frontmatter fields Path has always written and `path check` has always
validated, and nothing until now read them to answer the question everyone
actually asks.

The cost of not reading them was real. `path status` listed pending tasks in
identifier order, which meant a task it named might be unstartable and a reader
could not tell which, so choosing work meant opening every task file. That is a
lot of tokens spent rediscovering something already recorded.

Two distinctions this module refuses to collapse:

Waiting on a prerequisite is not the same as `status: blocked`. The first is
derived from the graph and clears itself when the prerequisite completes; the
second is a person declaring an obstacle, and clears only when a person acts.
Reporting them together would bury real blockers inside a list that mostly
resolves on its own.

Ranking is a heuristic and says so. Finishing the task that frees the most other
work first is defensible, not a law — what makes it usable is that it is
deterministic and explainable. An explicit human judgment about order, which is
what a batch's sequence is, outranks it.
"""

from __future__ import annotations

from pathlib import Path


def task_title(row: dict) -> str:
    """The task's recorded title, or one derived from its filename.

    `title` is ordinary OKF frontmatter rather than a `path:` field, so a row
    built from `path_meta` alone does not carry it. `tasks.summary` supplies it
    as `_title`; the filename slug is the fallback, and the empty string is the
    fallback to that, for hand-built rows in tests.
    """
    recorded = row.get("_title")
    if recorded:
        return str(recorded)
    path = row.get("_path")
    if not path:
        return ""
    parts = Path(path).stem.split("-", 2)
    return parts[2].replace("-", " ") if len(parts) == 3 else Path(path).stem


# -- batch progress ---------------------------------------------------------

# The order matters and is not alphabetical. A batch with work under way is
# in-progress even when another member is blocked, because the batch is moving;
# a batch is only blocked when nothing in it can move. Reversing these two would
# report a stalled batch for every batch that has one stuck member.
def derived_status(member_rows: list[dict]) -> str:
    """A batch's status, computed from its members. Never stored (F-54)."""
    statuses = [str(r.get("status") or "") for r in member_rows]
    if not statuses:
        return "pending"
    if all(s == "complete" for s in statuses):
        return "complete"
    if any(s == "in-progress" for s in statuses):
        return "in-progress"
    if any(s == "blocked" for s in statuses):
        return "blocked"
    return "pending"


def derived_completed(member_rows: list[dict]) -> str | None:
    """The batch's completion date: the last member to finish, or nothing."""
    if derived_status(member_rows) != "complete":
        return None
    dates = [str(r.get("completed")) for r in member_rows if r.get("completed")]
    return max(dates) if dates else None


def members(task_rows: list[dict], batch_id: str, sequence: list | None = None) -> list[dict]:
    """The tasks belonging to a batch, in the batch's intended order.

    Ordered by `sequence` where one is given, so the batch's own judgment about
    order wins. Anything claiming membership but missing from the sequence is
    appended rather than dropped — `path check` reports that disagreement, and
    silently hiding a task here would make the report the only place it shows.
    """
    owned = [r for r in task_rows if str(r.get("batch") or "") == batch_id]
    if not sequence:
        return sorted(owned, key=lambda r: str(r.get("id")))

    position = {str(t): i for i, t in enumerate(sequence)}
    return sorted(owned, key=lambda r: (position.get(str(r.get("id")), len(position)), str(r.get("id"))))


def rollup(task_rows: list[dict], batch_row: dict) -> dict:
    """One batch, summarised: derived status and member and point progress."""
    batch_id = str(batch_row.get("id"))
    member_rows = members(task_rows, batch_id, batch_row.get("sequence") or [])

    def points(rows):
        return sum(r["effort"] for r in rows if isinstance(r.get("effort"), int))

    done = [r for r in member_rows if r.get("status") == "complete"]
    return {
        "id": batch_id,
        "title": batch_row.get("_title") or batch_id,
        "status": derived_status(member_rows),
        "completed": derived_completed(member_rows),
        "tasks_done": len(done),
        "tasks_total": len(member_rows),
        "points_done": points(done),
        "points_total": points(member_rows),
        "sequence": [str(r.get("id")) for r in member_rows],
    }


# -- readiness --------------------------------------------------------------


def unblock_counts(rows: list[dict]) -> dict[str, int]:
    """For each task, how many others name it as a prerequisite.

    Counts every dependant, complete or not. A task that unblocked four others
    which are all now finished did that work, and the number is a fact about the
    graph rather than a live queue depth.
    """
    counts: dict[str, int] = {}
    for row in rows:
        for prerequisite in row.get("requires") or []:
            key = str(prerequisite)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _incomplete_prerequisites(row: dict, by_id: dict[str, dict]) -> list[str]:
    """Prerequisites that are not complete, including ones that do not exist.

    A `requires` naming a task that is not there is already a `path check`
    failure. Treating it as satisfied here would let a broken reference quietly
    promote a task to the top of the queue.
    """
    outstanding = []
    for prerequisite in row.get("requires") or []:
        other = by_id.get(str(prerequisite))
        if other is None or other.get("status") != "complete":
            outstanding.append(str(prerequisite))
    return outstanding


def _entry(row: dict, unblocks: int, needs: list[str] | None = None) -> dict:
    entry = {
        "id": str(row.get("id")),
        "title": task_title(row),
        "effort": row.get("effort"),
        "batch": row.get("batch") or None,
        "unblocks": unblocks,
        "implements": [str(r) for r in row.get("implements") or []],
        "status": row.get("status"),
    }
    # Repo-relative, not absolute: this entry is serialised into the status page,
    # and an absolute path would publish the author's home directory.
    if row.get("_relpath") or row.get("_path"):
        entry["file"] = str(row.get("_relpath") or row["_path"])
    if needs is not None:
        entry["needs"] = needs
    return entry


def readiness(task_rows: list[dict], batch_rollups: list[dict] | None = None) -> dict:
    """Split the backlog into what can be started and what cannot.

    Ranking, in order: a member of an in-progress batch, in that batch's own
    sequence; then the task unblocking the most others; then the lowest
    identifier. Only the first of those is a judgment someone actually made.
    """
    by_id = {str(r.get("id")): r for r in task_rows if r.get("id")}
    unblocks = unblock_counts(task_rows)

    # Position within an active batch. Only in-progress batches steer the queue:
    # a pending batch is a plan, not a commitment, and letting it reorder
    # everything would make the ranking depend on which batches merely exist.
    batch_order: dict[str, int] = {}
    for index, batch in enumerate(batch_rollups or []):
        if batch.get("status") != "in-progress":
            continue
        for position, task_id in enumerate(batch.get("sequence") or []):
            batch_order[str(task_id)] = index * 1000 + position

    ready, waiting, blocked, in_progress, complete = [], [], [], [], []

    for row in sorted(task_rows, key=lambda r: str(r.get("id"))):
        status = row.get("status")
        count = unblocks.get(str(row.get("id")), 0)

        if status == "complete":
            complete.append(_entry(row, count))
        elif status == "in-progress":
            in_progress.append(_entry(row, count))
        elif status == "blocked":
            blocked.append(_entry(row, count))
        elif status == "pending":
            outstanding = _incomplete_prerequisites(row, by_id)
            if outstanding:
                waiting.append(_entry(row, count, needs=outstanding))
            else:
                ready.append(_entry(row, count))

    ready.sort(
        key=lambda e: (
            batch_order.get(e["id"], 10**9),
            -e["unblocks"],
            e["id"],
        )
    )
    return {
        "ready": ready,
        "waiting": waiting,
        "blocked": blocked,
        "in_progress": in_progress,
        "complete": complete,
        "total": len(task_rows),
    }


def next_batch(readiness_result: dict, batch_rollups: list[dict]) -> dict | None:
    """The batch to be working in: the next ready task's, else one under way.

    The fallback matters more than it looks. A batch whose every member is
    started or waiting has no ready task in it, and returning nothing there
    would answer "which batch am I in" with silence at exactly the moment the
    answer is obvious. Complete batches are never returned, and a project with
    no live batch gets nothing rather than the first one in the list, because
    "next" has to mean something.
    """
    live = [b for b in batch_rollups if b.get("status") != "complete"]
    if not live:
        return None

    by_id = {str(b.get("id")): b for b in live}
    for entry in readiness_result["ready"]:
        if entry["batch"] and str(entry["batch"]) in by_id:
            return by_id[str(entry["batch"])]

    for entry in readiness_result["in_progress"]:
        if entry["batch"] and str(entry["batch"]) in by_id:
            return by_id[str(entry["batch"])]

    return next((b for b in live if b.get("status") == "in-progress"), None)


def _effort(entry: dict) -> str:
    return f"{entry['effort']} pts" if isinstance(entry.get("effort"), int) else "no estimate"


def render(readiness_result: dict, batch_rollups: list[dict] | None = None) -> str:
    """The next task, in enough detail to start it without opening anything else."""
    ready = readiness_result["ready"]
    if not ready:
        return _nothing_ready(readiness_result)

    entry = ready[0]
    lines = [f"{entry['id']}  {entry['title']}".rstrip() + f"   {_effort(entry)}"]

    if entry["batch"]:
        batch = next(
            (b for b in batch_rollups or [] if str(b.get("id")) == str(entry["batch"])), None
        )
        if batch:
            lines.append(
                f"  batch      {batch['id']} {batch['title']} "
                f"({batch['tasks_done']}/{batch['tasks_total']} done)"
            )
        else:
            lines.append(f"  batch      {entry['batch']}")
    if entry.get("file"):
        lines.append(f"  file       {entry['file']}")
    if entry["implements"]:
        lines.append(f"  implements {', '.join(entry['implements'])}")
    if entry["unblocks"]:
        dependants = [w["id"] for w in readiness_result["waiting"] if entry["id"] in w["needs"]]
        lines.append(f"  unblocks   {', '.join(dependants) or entry['unblocks']}")

    remaining = len(ready) - 1
    if remaining:
        lines.append(f"\n  {remaining} other task{'s' if remaining != 1 else ''} also ready.")
    return "\n".join(lines)


def render_batch(readiness_result: dict, batch_rollups: list[dict]) -> str:
    """The next batch, with its members in sequence order and their readiness."""
    batch = next_batch(readiness_result, batch_rollups)
    if batch is None:
        return _nothing_ready(readiness_result)

    state = {
        entry["id"]: entry
        for group in ("ready", "waiting", "blocked", "in_progress", "complete")
        for entry in readiness_result[group]
    }

    lines = [
        f"{batch['id']}  {batch['title']}   {batch['status']}   "
        f"{batch['tasks_done']}/{batch['tasks_total']} tasks, "
        f"{batch['points_done']}/{batch['points_total']} pts"
    ]
    for position, task_id in enumerate(batch["sequence"], start=1):
        entry = state.get(task_id)
        if entry is None:
            lines.append(f"  {position}. {task_id}  no longer in this project")
            continue
        note = {
            "complete": "done",
            "in-progress": "in progress",
            "blocked": "blocked",
            "pending": "ready",
        }.get(str(entry["status"]), "")
        if entry.get("needs"):
            note = f"needs {', '.join(entry['needs'])}"
        lines.append(
            f"  {position}. {entry['id']}  {entry['title']}".rstrip()
            + f"   {_effort(entry)}   {note}"
        )
    return "\n".join(lines)


def _nothing_ready(readiness_result: dict) -> str:
    """An empty queue is a fact about the backlog, not an error.

    Saying only "nothing is ready" would leave the reader to go find out why, so
    this names the nearest candidate and what it is waiting on.
    """
    if readiness_result["in_progress"]:
        ids = ", ".join(e["id"] for e in readiness_result["in_progress"])
        return f"Nothing new is ready. Already in progress: {ids}."

    if readiness_result["waiting"]:
        closest = min(readiness_result["waiting"], key=lambda e: (len(e["needs"]), e["id"]))
        return (
            "Nothing is ready to start.\n"
            f"  Closest: {closest['id']}  {closest['title']}".rstrip()
            + f"\n  Waiting on: {', '.join(closest['needs'])}"
        )

    if readiness_result["blocked"]:
        ids = ", ".join(e["id"] for e in readiness_result["blocked"])
        return f"Nothing is ready to start. Blocked: {ids} — see each task for the blocker."

    if readiness_result["total"] and len(readiness_result["complete"]) == readiness_result["total"]:
        return "Nothing is ready: every task is complete."
    return "Nothing is ready: there are no tasks yet. `path new task \"<title>\" --effort N`."
