"""Session close: the mechanical half checked, the judgment half asked.

`path close` writes a SESSION-CLOSE build log entry and regenerates
status.html. Implements the session-close half of blueprints/03-conventions.md
and the Definition of Done's split between what a machine can verify and what
it can only ask about — see blueprints/05-definition-of-done.md.

The Judgment checklist embedded in the entry is not hard-coded here. It is
parsed out of the Definition of Done itself, project-local copy first, so that
document stays the one place that list is written down. A future edit to that
file — a new Judgment item, or one reclassified as Mechanical — takes effect
here without a code change.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import check as check_mod
import decisions as decisions_mod
import metrics as metrics_mod
import okf
import path_status_page
import tasks as tasks_mod

JUDGMENT_ITEM_RE = re.compile(
    r"^-\s*\[ \]\s*\*\*\[Judgment[^\]]*\]\*\*\s*(.+)$", re.MULTILINE
)


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_dod(root: Path) -> Path | None:
    """The project's own Definition of Done if it has one, else Path's
    canonical copy. Matched by filename, not a fixed number — blueprint
    numbering is chosen per project (F-07), so lcm's is 04-, lcg's and Path's
    own are both 05-."""
    blueprints = root / "blueprints"
    if blueprints.is_dir():
        matches = sorted(blueprints.glob("*definition-of-done*.md"))
        if matches:
            return matches[0]
    canonical = Path(__file__).resolve().parent.parent / "blueprints" / "05-definition-of-done.md"
    return canonical if canonical.is_file() else None


def judgment_items(root: Path) -> list[str]:
    dod_path = find_dod(root)
    if dod_path is None:
        return []
    text = dod_path.read_text(encoding="utf-8")
    return [m.strip() for m in JUDGMENT_ITEM_RE.findall(text)]


def current_task(root: Path) -> str | None:
    project = okf.project_dir(root)
    agents = project / "AGENTS.md"
    if not agents.is_file():
        return None
    match = re.search(r"##\s+Current Task\s*\n+(.*?)(?:\n##|\Z)", agents.read_text(), re.DOTALL)
    if not match:
        return None
    line = match.group(1).strip()

    # A batch id wins over a task id on the same line. Once the Current Task
    # line could read "B-003 complete — ... (T-114 through T-121)", taking the
    # first T-NNN reported a finished member as the work in hand. The first id
    # on the line is the subject; the rest are the sentence talking about it.
    id_match = re.search(r"\bB-\d{3}\b|\bT-\d{3}\b", line)
    return id_match.group(0) if id_match else None


def completed_today(root: Path) -> list[dict]:
    today = _today()
    return [row for row in tasks_mod.summary(root)
            if row.get("status") == "complete" and str(row.get("completed")) == today]


def blocked_tasks(root: Path) -> list[dict]:
    return [row for row in tasks_mod.summary(root) if row.get("status") == "blocked"]


def tasks_with_issues(root: Path) -> list[tuple[str, list[dict]]]:
    result = []
    for row in tasks_mod.summary(root):
        issues = row.get("issues") or []
        if issues:
            result.append((str(row.get("id")), issues))
    return result


def build_entry_body(root: Path, check_summary: str, check_ok: bool) -> str:
    today = _today()
    completed = completed_today(root)
    blocked = blocked_tasks(root)
    open_decisions = decisions_mod.listing(root, open_only=True)
    issues = tasks_with_issues(root)
    current = current_task(root)
    items = judgment_items(root)

    lines = [f"# SESSION-CLOSE — {today}", ""]

    lines.append("## Completed This Session")
    lines.append("")
    if completed:
        for row in completed:
            lines.append(f"- {row.get('id')} — [fill in what was actually finished]")
    else:
        lines.append("[Fill this in — what was finished or meaningfully progressed.]")
    lines.append("")

    lines.append("## Current Task")
    lines.append("")
    lines.append(current or "None assigned.")
    lines.append("")

    lines.append("## Mechanical Definition of Done Check")
    lines.append("")
    lines.append(
        "Run automatically by `path close` via `path check` — see "
        "blueprints/05-definition-of-done.md for what this does and does not cover."
    )
    lines.append("")
    lines.append("```")
    lines.append(check_summary.strip() or "ok — every check passed.")
    lines.append("```")
    lines.append("")

    lines.append("## Judgment Definition of Done Review")
    lines.append("")
    lines.append(
        "Items `path check` cannot verify — a machine answering a question of fact does not "
        "need this list; these need a person or an agent to actually think. Go through each one "
        "for every task completed this session, not just the ones that feel uncertain."
    )
    lines.append("")
    if items:
        for item in items:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("[No Definition of Done found — see blueprints/05-definition-of-done.md.]")
    lines.append("")

    lines.append("## State at Close")
    lines.append("")
    lines.append("[Fill this in — what is working, what is mid-flight.]")
    lines.append("")

    lines.append("## Next Session — Start Here")
    lines.append("")
    lines.append("[Fill this in — the specific first action, concrete enough to skip re-reading everything.]")
    lines.append("")

    lines.append("## Blockers / Open Questions")
    lines.append("")
    any_blockers = False
    if blocked:
        any_blockers = True
        for row in blocked:
            lines.append(f"- {row.get('id')} is blocked.")
    if open_decisions:
        any_blockers = True
        for row in open_decisions:
            lines.append(f"- Open decision ({row['age_days']}d): {row['question']}")
    if not any_blockers:
        lines.append("None.")
    lines.append("")

    lines.append("## Process Improvement Recommendations")
    lines.append("")
    if issues:
        lines.append(
            "Tasks with logged issues this session — for each, decide whether a gap in the "
            "requirements, blueprints, or the task itself let it through, or whether it was "
            "ordinary execution-time discovery with no documentation gap behind it:"
        )
        lines.append("")
        for task_id, task_issues in issues:
            lines.append(f"- **{task_id}**")
            for issue in task_issues:
                lines.append(f"  - {issue.get('date')}: {issue.get('note')} "
                              f"[fill in: gap, or not?]")
    else:
        lines.append("No issues were logged this session.")
    lines.append("")

    return "\n".join(lines)


def entry_path(root: Path) -> Path:
    build_log = root / "build-log"
    build_log.mkdir(exist_ok=True)
    today = _today()
    base = f"{today}-session-close"
    candidate = build_log / f"{base}.md"
    n = 2
    while candidate.is_file():
        candidate = build_log / f"{base}-{n}.md"
        n += 1
    return candidate


def close(root: Path, output=print) -> Path:
    exit_code, findings = check_mod.run(root, task_id=None, write_proof=False)
    if findings:
        check_summary = "\n".join(str(f) for f in findings)
        check_summary += f"\n\n{len(findings)} finding(s)."
    else:
        check_summary = "ok — every check passed."

    body = build_entry_body(root, check_summary, exit_code == 0)
    path = entry_path(root)

    doc = okf.Doc(
        path=path,
        meta={
            "type": "Build Log Entry",
            "title": f"Session close — {_today()}",
            "description": "",
            "tags": ["session-close"],
            "timestamp": _now(),
            "path": {"entry_type": "SESSION-CLOSE", "date": _today()},
        },
        body="\n" + body,
    )
    okf.save(doc)
    okf.rebuild_build_log_index(root / "build-log", okf.project_dir(root).name)

    status_data = metrics_mod.build(root)
    status_path = root / "status.html"
    status_path.write_text(path_status_page.render_html(status_data), encoding="utf-8")

    output(f"Session-close entry: {path}")
    output(f"Regenerated: {status_path}")
    if exit_code != 0:
        output(f"\npath check found {len(findings)} issue(s) — see the entry, or run `path check`.")
    output("\nOpen the entry and fill in: Completed This Session, State at Close, "
           "Next Session, and every Judgment item.")
    return path
