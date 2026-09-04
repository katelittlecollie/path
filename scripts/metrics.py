"""Metrics, assembled from frontmatter.

Implements F-32 and F-33. Nothing here parses prose. The previous version of
this logic scraped Markdown bullets with regular expressions — `- **2026-07-16**
Status at time of change: pending — ...` — and a stray em-dash silently dropped
a data point. Every figure now comes from a documented frontmatter path that a
person can query themselves with yq; see blueprints/06-okf-mapping.md.

On provenance: some values are derived rather than recorded. A task migrated
from a work order may carry an effort estimate assigned retrospectively by a
model, or a completion date inferred from a git commit. Those are marked at
`path.effort_source` and `path.completed_source`, and this module counts them
so that a chart built on estimates cannot be mistaken for one built on
measurements. Absence of a source key means the value was recorded at the time,
which is the only kind of number that is really evidence.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import batches as batches_mod
import decisions as decisions_mod
import next as next_mod
import okf
import tasks as tasks_mod

# The status a task was in when its scope changed determines the impact of that
# change. Classifying from the recorded status rather than asking for a
# judgment is what stops the volatility chart from being editorialised.
IMPACT_BY_STATUS = {"pending": "low", "in-progress": "medium", "complete": "high"}

DERIVED_SOURCES = ("estimated", "inferred-git")

# The trailing window the rate is measured over. Two weeks is short enough to
# reflect what is happening now and long enough to survive one quiet week. It
# stays a parameter, and whatever value is used is reported alongside the
# figure, because a rate whose window is unstated is not a rate.
DEFAULT_WINDOW_DAYS = 14

# Below this many completions inside the window there is no rate to speak of.
# One point establishes a position, not a slope.
MIN_COMPLETIONS_FOR_RATE = 2


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _is_derived(meta: dict, field: str) -> bool:
    return str(meta.get(f"{field}_source") or "") in DERIVED_SOURCES


def burnup(rows: list[dict]) -> dict:
    """Total backlog against completed points, plotted at each completion date."""
    backlog_total = sum(r["effort"] for r in rows if isinstance(r.get("effort"), int))

    completed = sorted(
        (
            r for r in rows
            if r.get("status") == "complete"
            and _parse_date(r.get("completed"))
            and isinstance(r.get("effort"), int)
        ),
        key=lambda r: str(r["completed"]),
    )

    points, cumulative = [], 0
    for row in completed:
        cumulative += row["effort"]
        points.append(
            {
                "date": str(row["completed"]),
                "completed": cumulative,
                "remaining": backlog_total - cumulative,
                "task": row.get("id"),
                "derived": _is_derived(row, "effort") or _is_derived(row, "completed"),
            }
        )

    if not points:
        points.append(
            {
                "date": date.today().isoformat(),
                "completed": 0,
                "remaining": backlog_total,
                "task": None,
                "derived": False,
            }
        )

    return {"backlog_total": backlog_total, "points": points}


def velocity(rows: list[dict], window_days: int = DEFAULT_WINDOW_DAYS, today: date | None = None) -> dict:
    """Points completed per week over a trailing window (F-56).

    Deliberately narrow in what it claims. This is the rate at which *this
    backlog* has been consumed lately, which is what the projection needs. It is
    not a measure of anyone's capacity, and F-57 says so out loud, because the
    same arithmetic reads as both and only one of them is defensible.

    The window is returned with the number. A rate whose basis is unstated
    invites the reader to supply their own, which is how "11 points a week"
    quietly becomes an all-time average in someone's head.
    """
    end = today or date.today()
    start = end - timedelta(days=window_days)

    inside = [
        row
        for row in rows
        if row.get("status") == "complete"
        and (completed := _parse_date(row.get("completed")))
        and start < completed <= end
    ]

    points = sum(r["effort"] for r in inside if isinstance(r.get("effort"), int))
    sufficient = len(inside) >= MIN_COMPLETIONS_FOR_RATE

    return {
        "window_days": window_days,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "tasks": len(inside),
        "points": points,
        "points_per_week": round(points * 7 / window_days, 1) if sufficient else None,
        "sufficient": sufficient,
        "derived": any(
            _is_derived(r, "effort") or _is_derived(r, "completed") for r in inside
        ),
    }


def forecast(rows: list[dict], window_days: int = DEFAULT_WINDOW_DAYS, today: date | None = None) -> dict:
    """The remaining backlog projected against the recent rate (F-56, F-57).

    When the window holds too few completions, this says so and stops. The
    tempting alternative is to widen the window until it holds something, which
    produces a number whose basis moved without saying so — worse than no number,
    because the reader believes they are looking at the recent rate.

    Unestimated tasks are counted and reported rather than treated as zero. A
    backlog with holes in it cannot be projected honestly, and the projection
    should be read next to the size of the hole.
    """
    rate = velocity(rows, window_days, today)
    remaining = [r for r in rows if r.get("status") != "complete"]
    remaining_points = sum(r["effort"] for r in remaining if isinstance(r.get("effort"), int))
    unestimated = sorted(
        str(r["id"]) for r in remaining if not isinstance(r.get("effort"), int) and r.get("id")
    )

    result = {
        "window_days": window_days,
        "points_per_week": rate["points_per_week"],
        "remaining_tasks": len(remaining),
        "remaining_points": remaining_points,
        "unestimated": unestimated,
        "weeks_remaining": None,
        "projected_date": None,
        "sufficient": rate["sufficient"],
        "derived": rate["derived"] or any(_is_derived(r, "effort") for r in remaining),
    }

    if not rate["sufficient"] or not rate["points_per_week"]:
        return result

    weeks = remaining_points / rate["points_per_week"]
    end = today or date.today()
    result["weeks_remaining"] = round(weeks, 1)
    result["projected_date"] = (end + timedelta(days=round(weeks * 7))).isoformat()
    return result


def volatility(rows: list[dict]) -> list[dict]:
    """Change log entries in weekly buckets, stacked by impact."""
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        for entry in row.get("change_log") or []:
            when = _parse_date(entry.get("date"))
            if not when:
                continue
            monday = (when - timedelta(days=when.weekday())).isoformat()
            impact = IMPACT_BY_STATUS.get(entry.get("status_at_change"), "medium")
            buckets.setdefault(monday, {"low": 0, "medium": 0, "high": 0})
            buckets[monday][impact] += 1
    return [{"period": period, **counts} for period, counts in sorted(buckets.items())]


def drift(rows: list[dict]) -> list[dict]:
    """Drift entries, plus issues logged after a task was called complete.

    A bug found after completion is drift whether or not anyone remembered to
    file it as such — the boundary moved after the work was declared finished.
    Deriving it from the dates rather than trusting the label means it cannot be
    quietly under-reported.
    """
    events = []
    for row in rows:
        task_id = row.get("id")

        for entry in row.get("drift_log") or []:
            events.append(
                {
                    "date": str(entry.get("date")),
                    "type": entry.get("kind"),
                    "effort": entry.get("effort_to_correct") or 2,
                    "task": task_id,
                    "description": entry.get("note") or "",
                }
            )

        completed_on = _parse_date(row.get("completed"))
        if not completed_on:
            continue
        for issue in row.get("issues") or []:
            found_on = _parse_date(issue.get("date"))
            if found_on and found_on > completed_on:
                events.append(
                    {
                        "date": str(issue["date"]),
                        "type": "post-completion-bug",
                        "effort": 2,
                        "task": task_id,
                        "description": issue.get("note") or "",
                    }
                )

    events.sort(key=lambda e: e["date"])
    return events


def decision_rows(root: Path) -> list[dict]:
    """Open decisions first, oldest first within each group."""
    rows = []
    for row in decisions_mod.listing(root):
        rows.append(
            {
                "question": row.get("question"),
                "task": row.get("related_task"),
                "raised": row.get("raised"),
                "resolved": row.get("resolved"),
                "age_days": row.get("age_days"),
                "open": not row.get("resolved"),
            }
        )
    rows.sort(key=lambda r: (not r["open"], -(r["age_days"] or 0)))
    return rows


def provenance(rows: list[dict]) -> dict:
    """How much of this is measured, and how much is derived.

    Published alongside the numbers rather than in a comment, because a reader
    who cannot tell an estimate from a measurement will treat both as fact.
    """
    estimated_effort = [r["id"] for r in rows if _is_derived(r, "effort")]
    inferred_completed = [r["id"] for r in rows if _is_derived(r, "completed")]
    return {
        "tasks_total": len(rows),
        "effort_estimated": sorted(str(i) for i in estimated_effort if i),
        "completed_inferred": sorted(str(i) for i in inferred_completed if i),
        "any_derived": bool(estimated_effort or inferred_completed),
    }


def status_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row.get("status"))] = counts.get(str(row.get("status")), 0) + 1
    return dict(sorted(counts.items()))


def build(root: Path) -> dict:
    """Every metric, from frontmatter, in one document."""
    rows = tasks_mod.summary(root)
    batch_rollups = batches_mod.rollups(root, rows)
    # Readiness is computed before the private keys are dropped, because it is
    # the one consumer that wants the file path — `path next` names the file to
    # open, which is most of what makes it cheaper than reading the directory.
    ready = next_mod.readiness(rows, batch_rollups)
    for row in rows:
        row.pop("_path", None)
        row.pop("_title", None)

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "project": okf.project_dir(root).name,
        "tasks": {
            "total": len(rows),
            "by_status": status_counts(rows),
            "without_effort": sorted(
                str(r["id"]) for r in rows if not isinstance(r.get("effort"), int) and r.get("id")
            ),
        },
        "batches": batch_rollups,
        "readiness": ready,
        "burnup": burnup(rows),
        "velocity": velocity(rows),
        "forecast": forecast(rows),
        "volatility": volatility(rows),
        "decisions": decision_rows(root),
        "drift": drift(rows),
        "provenance": provenance(rows),
    }


def portfolio(project_roots: list[Path]) -> dict:
    """Metrics for several projects at once, for a portfolio view."""
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "projects": [build(root) for root in project_roots],
    }


def find_projects(start: Path) -> list[Path]:
    """Every Path project directly under `start`."""
    found = []
    for child in sorted(p for p in start.iterdir() if p.is_dir()):
        root = okf.find_project_root(child)
        if root and root not in found and child in (root, root.parent):
            found.append(root)
    return found
