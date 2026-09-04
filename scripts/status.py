"""`path status` — project or portfolio status, straight from frontmatter.

The terminal counterpart to status.html. Same source (scripts/metrics.py over
task frontmatter), shaped for a glance in a shell rather than a browser: where
the backlog stands, what can actually be started, what is grouped with what, and
when it plausibly lands. Deterministic only — phase and narrative live in
AGENTS.md, and this never invents either.

The queue used to be pending tasks in identifier order, which meant it could
name a task that was unstartable and give the reader no way to tell. It now
reports readiness, computed once in `next.readiness` and shared with `path next`
and the tasks index, so the three cannot answer the same question differently.

Every function here takes a list of frontmatter rows so the grouping and
ordering can be checked with hand-built dicts, the same way scripts/metrics.py
is tested.
"""

from __future__ import annotations

from pathlib import Path

import batches as batches_mod
import metrics
import next as next_mod
import okf
import tasks as tasks_mod

# The order a reader wants them in: what is being worked, what is stuck, what is
# queued, then the done pile. Any status outside this list is appended in
# whatever order it sorts, so an unfamiliar value is shown rather than dropped.
STATUS_ORDER = ["in-progress", "blocked", "pending", "complete"]

# How many entries to name before collapsing the rest to a count. The queue is a
# glance, not the whole backlog.
SHOWN = 5

# The recorded title first, the filename slug second. Defined in `next` because
# that is where the queue is built; re-exported here so there is one of it.
task_title = next_mod.task_title


def _counts_line(counts: dict[str, int]) -> str:
    ordered = [(s, counts[s]) for s in STATUS_ORDER if s in counts]
    ordered += [(s, n) for s, n in counts.items() if s not in STATUS_ORDER]
    return ", ".join(f"{n} {s}" for s, n in ordered)


def _effort(entry: dict) -> str:
    return f"{entry['effort']} pts" if isinstance(entry.get("effort"), int) else "no estimate"


def _section(label: str, lines: list[str]) -> list[str]:
    """A heading with entries, or nothing at all.

    An empty heading is worse than a missing one: it asks the reader to notice
    that nothing is under it. A glance should carry only what is true.
    """
    return [f"\n  {label}:", *lines] if lines else []


def queue_lines(rows: list[dict], batch_rollups: list[dict] | None = None) -> list[str]:
    """Counts, then the actionable queue: in progress, blocked, batches, ready, waiting."""
    if not rows:
        return ["  no tasks yet"]

    ready = next_mod.readiness(rows, batch_rollups)
    lines = [f"  {len(rows)} tasks — {_counts_line(metrics.status_counts(rows))}"]

    def named(entries):
        out = [f"    {e['id']}  {e['title']}".rstrip() for e in entries[:SHOWN]]
        if len(entries) > SHOWN:
            out.append(f"    … and {len(entries) - SHOWN} more")
        return out

    lines += _section("In progress", named(ready["in_progress"]))
    lines += _section("Blocked", named(ready["blocked"]))

    live = [b for b in (batch_rollups or []) if b["status"] != "complete"]
    lines += _section(
        "Batches",
        [
            f"    {b['id']}  {b['title']}   {b['status']}   "
            f"{b['tasks_done']}/{b['tasks_total']} tasks, "
            f"{b['points_done']}/{b['points_total']} pts"
            for b in live
        ],
    )

    ready_lines = []
    for entry in ready["ready"][:SHOWN]:
        trailer = [_effort(entry)]
        if entry["batch"]:
            trailer.append(str(entry["batch"]))
        if entry["unblocks"]:
            trailer.append(f"unblocks {entry['unblocks']}")
        ready_lines.append(f"    {entry['id']}  {entry['title']}".rstrip() + "   " + "   ".join(trailer))
    if len(ready["ready"]) > SHOWN:
        ready_lines.append(f"    … and {len(ready['ready']) - SHOWN} more ready")
    lines += _section("Ready now", ready_lines)

    # Waiting is not the same as blocked, and is reported apart from it: this
    # clears itself when a prerequisite completes, and blocked does not.
    if ready["waiting"]:
        shown = ready["waiting"][:SHOWN]
        summary = ", ".join(f"{e['id']} (needs {', '.join(e['needs'])})" for e in shown)
        if len(ready["waiting"]) > SHOWN:
            summary += f", … and {len(ready['waiting']) - SHOWN} more"
        lines.append(f"\n  Waiting on prerequisites:\n    {len(ready['waiting'])} tasks — {summary}")

    return lines


def rate_lines(rows: list[dict]) -> list[str]:
    """The recent rate and what it projects — or a plain statement that it cannot.

    The refusal is deliberate and is the reason this is worth printing at all. A
    window with too little in it produces no number here; widening it silently
    until it held something would move the basis of the figure without saying so,
    and the reader would believe they were looking at the recent rate (F-56).
    """
    velocity = metrics.velocity(rows)
    forecast = metrics.forecast(rows)
    window = velocity["window_days"]

    if not velocity["sufficient"]:
        return [
            f"  rate        not enough completions in the last {window} days to measure "
            f"({velocity['tasks']} in that window)"
        ]

    lines = [
        f"  rate        {velocity['points_per_week']} pts/week over the last {window} days "
        f"({velocity['tasks']} tasks)"
    ]
    if forecast["projected_date"]:
        lines.append(
            f"  forecast    ~{forecast['weeks_remaining']} weeks remaining — "
            f"around {forecast['projected_date']}"
        )
    if forecast["unestimated"]:
        lines.append(
            f"              {len(forecast['unestimated'])} remaining task(s) carry no estimate, "
            "so this is an under-count"
        )
    return lines


def project_lines(root: Path) -> list[str]:
    rows = tasks_mod.summary(root)
    rollups = batches_mod.rollups(root, rows)
    burn = metrics.burnup(rows)
    done_points = burn["points"][-1]["completed"] if burn["points"] else 0
    total_points = burn["backlog_total"]
    done_tasks = sum(1 for r in rows if r.get("status") == "complete")
    decisions = metrics.decision_rows(root)
    open_decisions = sum(1 for d in decisions if d["open"])
    prov = metrics.provenance(rows)

    lines = [okf.project_dir(root).name]
    lines.extend(queue_lines(rows, rollups))

    pct = f" ({round(done_points / total_points * 100)}%)" if total_points else ""
    lines.append(
        f"\n  backlog     {done_tasks}/{len(rows)} tasks, "
        f"{done_points}/{total_points} points{pct}"
    )
    lines.extend(rate_lines(rows))
    lines.append(f"  decisions   {open_decisions} open of {len(decisions)}")

    missing = sorted(
        str(r["id"]) for r in rows if not isinstance(r.get("effort"), int) and r.get("id")
    )
    if missing:
        lines.append(
            f"\n  {len(missing)} without an effort estimate: "
            + ", ".join(missing[:8])
            + (" …" if len(missing) > 8 else "")
        )

    if prov["any_derived"] or metrics.forecast(rows)["derived"]:
        bits = []
        if prov["effort_estimated"]:
            bits.append(f"{len(prov['effort_estimated'])} effort estimates model-assigned")
        if prov["completed_inferred"]:
            bits.append(f"{len(prov['completed_inferred'])} completion dates git-inferred")
        if bits:
            lines.append("\n  Some figures are derived, not measured: " + "; ".join(bits) + ".")

    return lines


def render(root: Path) -> str:
    return "\n".join(project_lines(root))


def render_portfolio(roots: list[Path]) -> str:
    """One line per project — the numbers you triage a portfolio on."""
    header = f"Portfolio — {len(roots)} project{'s' if len(roots) != 1 else ''}"
    summaries = []
    for root in roots:
        rows = tasks_mod.summary(root)
        counts = metrics.status_counts(rows)
        burn = metrics.burnup(rows)
        velocity = metrics.velocity(rows)
        summaries.append(
            {
                "name": okf.project_dir(root).name,
                "done": burn["points"][-1]["completed"] if burn["points"] else 0,
                "total": burn["backlog_total"],
                "active": counts.get("in-progress", 0),
                "pending": counts.get("pending", 0),
                "open_dec": sum(1 for d in metrics.decision_rows(root) if d["open"]),
                "rate": f"{velocity['points_per_week']} pts/wk"
                if velocity["sufficient"]
                else "no recent rate",
            }
        )

    width = max((len(s["name"]) for s in summaries), default=0)
    lines = [header]
    for s in summaries:
        lines.append(
            f"  {s['name']:<{width}}  {s['done']}/{s['total']} pts   "
            f"{s['active']} in-progress, {s['pending']} pending   "
            f"{s['rate']}   {s['open_dec']} open decisions"
        )
    return "\n".join(lines)
