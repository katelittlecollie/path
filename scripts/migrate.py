"""Work orders to OKF tasks.

This module contains the only parser for the legacy work order format that
still exists, and it is meant to be thrown away once every project has been
migrated. Everything else in Path reads frontmatter.

Two principles govern what happens here:

  Report, do not guess. A field that was never recorded stays empty and is
  named in the report. The one exception is deliberate and marked — see
  `path.effort_source` and `path.completed_source` in the OKF mapping, and the
  reasoning in build-log/2026-07-16-derived-metrics.md.

  Refuse rather than half-finish. Migration touches every file in a project.
  It requires a clean git tree so `git reset --hard HEAD && git clean -fd` is
  a real undo, and it does nothing at all unless it can do the whole thing.

A legacy project's docs, at the time it needs migrating, are nested at the old
bare `path/` — not `.path/`, since the dotfile convention did not exist yet
when that project was set up. Rename it first (`git mv path .path`), then run
`path migrate`: `okf.find_project_root` only recognizes `.path/` now, and
everything downstream — the work-orders lookup, the tasks/ output — resolves
correctly relative to whatever root it returns.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import okf
import tasks as tasks_mod

WO_FILENAME_RE = re.compile(r"\AWO-(\d{3,})-(.+)\.md\Z")
WO_TITLE_RE = re.compile(r"^#\s*WO-\d{3,}\s*[—–-]\s*(.+?)\s*$", re.MULTILINE)

# A legacy project predates the dotfile convention, so its own prose may still
# say bare `path/requirements/...` rather than `.path/requirements/...`. Scoped
# to `path/` immediately followed by one of Path's own subpaths — not a bare
# `\bpath/\b` — so it can't touch an unrelated sentence that happens to use the
# word "path". The negative lookbehind stops it from re-dotting a reference
# that already correctly says `.path/...`.
LEGACY_PATH_PREFIX_RE = re.compile(
    r"(?<![.\w])path/(?=requirements/|blueprints/|tasks/|build-log/|work-orders/|decisions-log\.md)"
)
FIELD_RE_TEMPLATE = r"^\*\*{name}:\*\*\s*(.*?)\s*$"
DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")

CHANGE_RE = re.compile(
    r"^-\s*\*\*\[?(\d{4}-\d{2}-\d{2})\]?\*\*\s*Status at time of change:\s*"
    r"\[?([a-zA-Z-]+)\]?\s*[—–-]+\s*(.*)$"
)
DRIFT_RE = re.compile(
    r"^-\s*\*\*\[?(\d{4}-\d{2}-\d{2})\]?\*\*\s*Type:\s*\[?([a-zA-Z-]+)\]?\s*[—–-]+\s*"
    r"(.*?)\s*[—–-]+\s*Effort to correct:\s*\[?(\d)\]?\s*$"
)
ISSUE_RE = re.compile(r"^-\s*\*\*\[?(\d{4}-\d{2}-\d{2})\]?\*\*\s*(.*)$")

LOG_HEADINGS = ("Change Log", "Drift Log", "Issues Found During Execution")

# Placeholder rows in a freshly scaffolded template are not data. Migrating
# them would manufacture a decision nobody ever raised.
PLACEHOLDER_MARKERS = ("[One-line question]", "YYYY-MM-DD", "[WO-NNN or —]", "[Description")

DOC_TYPE_BY_DIR = {
    "requirements": "Requirement",
    "blueprints": "Blueprint",
    "build-log": "Build Log Entry",
}


class MigrationError(Exception):
    """Migration cannot proceed."""


@dataclass
class Report:
    """What migration did, or would do. Printed for a dry run; kept for the log."""

    work_orders: int = 0
    renames: list[tuple[str, str]] = field(default_factory=list)
    frontmatter_added: list[str] = field(default_factory=list)
    rewrites: list[tuple[str, int]] = field(default_factory=list)
    decisions_migrated: int = 0
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)


# ── git ───────────────────────────────────────────────────────────────────────


def _rel(path: Path, root: Path) -> str:
    """A path as the reader would type it, relative to the project's parent."""
    try:
        return str(path.relative_to(okf.project_dir(root)))
    except ValueError:
        return str(path)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise MigrationError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def repo_root(start: Path) -> Path:
    try:
        return Path(_git(start, "rev-parse", "--show-toplevel").strip())
    except MigrationError as exc:
        raise MigrationError(f"{start} is not inside a git repository: {exc}") from exc


def require_clean_tree(repo: Path) -> None:
    """A clean tree is what makes the undo real.

    The undo is `git reset --hard HEAD && git clean -fd`, not `git checkout .`.
    Migration stages its work — the renames go through `git rm --cached` and
    `git add` so that git records them as renames rather than as a delete plus
    an unrelated add. `git checkout .` restores the working tree *from the
    index*, and the index already agrees the old files are gone, so it silently
    restores almost nothing. Learned the hard way.
    """
    dirty = _git(repo, "status", "--porcelain").strip()
    if dirty:
        count = len(dirty.splitlines())
        raise MigrationError(
            f"{repo} has {count} uncommitted change{'s' if count != 1 else ''}.\n"
            "Migration rewrites every documentation file in the project. A clean tree is what\n"
            "makes `git reset --hard HEAD` a real undo, and without one there is no way to tell\n"
            "your work from the migration's. Commit or stash first."
        )


def completion_date_from_git(repo: Path, path: Path, report: Report) -> str | None:
    """The date the file first appeared with a complete status.

    Walks the file's commits oldest-first and returns the first whose content
    records completion. For a file that was added already marked complete —
    which is most of them — that is the date it entered the repository, not the
    date the work finished. That distinction is why the value is marked
    `completed_source: inferred-git` and why the status page says so.
    """
    try:
        relative = str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        report.warn(f"{path}: outside the repository, cannot infer a completion date")
        return None
    try:
        log = _git(repo, "log", "--reverse", "--format=%H %ad", "--date=short", "--", relative)
    except MigrationError:
        return None

    for line in log.splitlines():
        if not line.strip():
            continue
        sha, when = line.split(" ", 1)
        try:
            content = _git(repo, "show", f"{sha}:{relative}")
        except MigrationError:
            continue
        status = _field(content, "Status")
        if status and status.strip().lower() == "complete":
            return when.strip()

    report.warn(f"{relative}: could not infer a completion date from git history")
    return None


# ── legacy parsing ────────────────────────────────────────────────────────────


def _field(text: str, name: str) -> str | None:
    match = re.search(FIELD_RE_TEMPLATE.format(name=re.escape(name)), text, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    # An untouched template leaves the option list in place.
    if not value or "|" in value or value.startswith("["):
        return None
    return value


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return ""
    rest = text[match.end():]
    following = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: following.start()] if following else rest


def _strip_header_block(text: str) -> str:
    """Drop the `---` fenced field block; its contents become frontmatter."""
    lines = text.splitlines()
    fences = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(fences) >= 2:
        del lines[fences[0]: fences[1] + 1]
    return "\n".join(lines)


def _strip_sections(text: str, headings: tuple[str, ...]) -> str:
    """Remove body sections whose data now lives in frontmatter (F-30)."""
    for heading in headings:
        pattern = re.compile(
            rf"^##\s+{re.escape(heading)}\s*$.*?(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL
        )
        text = pattern.sub("", text)
    return text


def parse_change_log(text: str, wo_id: str, report: Report) -> list[dict]:
    entries = []
    for line in _section(text, "Change Log").splitlines():
        line = line.strip()
        if not line.startswith("-") or "[What changed" in line:
            continue
        match = CHANGE_RE.match(line)
        if match:
            entries.append(
                {"date": match.group(1), "status_at_change": match.group(2).lower(),
                 "note": match.group(3).strip()}
            )
        elif re.match(r"^-\s*\*\*\d{4}", line):
            report.warn(f"{wo_id}: unparseable change log line, left for a human: {line[:70]}")
    return entries


def parse_drift_log(text: str, wo_id: str, report: Report) -> list[dict]:
    entries = []
    for line in _section(text, "Drift Log").splitlines():
        line = line.strip()
        if not line.startswith("-") or "[Description]" in line:
            continue
        match = DRIFT_RE.match(line)
        if match:
            entries.append(
                {"date": match.group(1), "kind": match.group(2).lower(),
                 "effort_to_correct": int(match.group(4)), "note": match.group(3).strip()}
            )
        elif re.match(r"^-\s*\*\*\d{4}", line):
            report.warn(f"{wo_id}: unparseable drift log line, left for a human: {line[:70]}")
    return entries


def parse_issues(text: str, wo_id: str, report: Report) -> list[dict]:
    entries = []
    for line in _section(text, "Issues Found During Execution").splitlines():
        line = line.strip()
        if not line.startswith("-") or "[Description of the issue" in line:
            continue
        match = ISSUE_RE.match(line)
        if match:
            entries.append({"date": match.group(1), "note": match.group(2).strip(),
                            "resolution": None})
        elif re.match(r"^-\s*\*\*\d{4}", line):
            report.warn(f"{wo_id}: unparseable issue line, left for a human: {line[:70]}")
    return entries


# ── the migration ─────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_date(value: str | None) -> str | None:
    if value and DATE_RE.match(value):
        return value
    return None


def convert_work_order(
    repo: Path,
    root: Path,
    path: Path,
    estimates: dict[str, int],
    report: Report,
) -> tuple[Path, okf.Doc]:
    text = path.read_text(encoding="utf-8")
    match = WO_FILENAME_RE.match(path.name)
    if not match:
        raise MigrationError(f"{path.name} is not a work order filename")

    number, slug = match.group(1), match.group(2)
    wo_id, task_id = f"WO-{number}", f"T-{number}"

    title_match = WO_TITLE_RE.search(text)
    title = title_match.group(1).strip() if title_match else slug.replace("-", " ").capitalize()

    status_raw = _field(text, "Status") or ""
    # Two lcm work orders say "Complete" with a capital C. The old parser
    # compared without normalising, so both were silently dropped from every
    # metric it produced.
    status = status_raw.strip().lower()
    if status_raw and status_raw != status:
        report.note(f"{wo_id}: normalised status {status_raw!r} to {status!r}")
    if status not in ("pending", "in-progress", "complete", "blocked"):
        report.warn(f"{wo_id}: unrecognised status {status_raw!r}, defaulting to pending")
        status = "pending"

    effort_raw = _field(text, "Effort Estimate")
    effort = int(effort_raw) if effort_raw and effort_raw.isdigit() else None
    effort_source = None
    if effort is None and wo_id in estimates:
        effort = estimates[wo_id]
        effort_source = "estimated"
    elif effort is None:
        report.warn(f"{wo_id}: no effort estimate recorded and none supplied")

    created = _clean_date(_field(text, "Created"))
    updated = _clean_date(_field(text, "Updated")) or created
    completed = _clean_date(_field(text, "Completed"))
    completed_source = None

    if status == "complete" and not completed:
        completed = completion_date_from_git(repo, path, report)
        if completed:
            completed_source = "inferred-git"
    if status != "complete" and completed:
        report.warn(f"{wo_id}: completed date {completed} but status {status!r}; clearing the date")
        completed = None

    body = _strip_sections(_strip_header_block(text), LOG_HEADINGS)
    body = re.sub(r"^#\s*WO-\d{3,}\s*[—–-]\s*", "# ", body, count=1, flags=re.MULTILINE)
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"

    meta_path = {
        "id": task_id,
        "status": status,
        "effort": effort,
        "created": created,
        "updated": updated or created,
        "completed": completed,
        "project": _field(text, "Project") or okf.project_dir(root).name,
        "drafted_by": _field(text, "Drafted By") or "Unknown",
        "completed_by": [v] if (v := _field(text, "Completed By")) else [],
        "requires": [],
        "implements": [],
        "change_log": parse_change_log(text, wo_id, report),
        "drift_log": parse_drift_log(text, wo_id, report),
        "issues": parse_issues(text, wo_id, report),
        "migrated_from": wo_id,
        "proof": {"checked_at": None, "result": None},
    }
    if effort_source:
        meta_path["effort_source"] = effort_source
    if completed_source:
        meta_path["completed_source"] = completed_source

    doc = okf.Doc(
        path=root / "tasks" / f"{task_id}-{slug}.md",
        meta={
            "type": "Task",
            "title": title,
            "description": "",
            "tags": [],
            "timestamp": _now(),
            "path": meta_path,
        },
        body="\n" + body,
    )
    return path, doc


def convert_decisions(root: Path, report: Report) -> okf.Doc | None:
    """The table becomes frontmatter rows. `Age (days)` is dropped: it was a
    stored copy of a computed value, and the status page always recomputed it."""
    path = root / "decisions-log.md"
    if not path.is_file():
        return None

    text = path.read_text(encoding="utf-8")
    rows, body_lines = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            body_lines.append(line)
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 4 or cells[0].lower() == "decision" or set(cells[0]) <= set("-: "):
            continue
        if any(marker in stripped for marker in PLACEHOLDER_MARKERS):
            report.note("decisions-log.md: skipped an unfilled template row")
            continue
        raised = _clean_date(cells[2])
        if not raised:
            report.warn(f"decisions-log.md: row with no raised date, skipped: {cells[0][:50]}")
            continue
        related = cells[1]
        if related and re.match(r"\AWO-\d{3,}\Z", related):
            related = related.replace("WO-", "T-")
        elif related in ("—", "-", ""):
            related = None
        rows.append(
            {
                "question": cells[0],
                "related_task": related,
                "raised": raised,
                "resolved": _clean_date(cells[3]),
                "answer": None,
            }
        )

    report.decisions_migrated = len(rows)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(body_lines)).strip() + "\n"
    body = body.replace("Related WO", "Related Task").replace("work order", "task")

    return okf.Doc(
        path=path,
        meta={
            "type": "Decision Log",
            "title": f"{okf.project_dir(root).name} — Decisions Log",
            "description": "Open questions raised to the project owner that a task cannot proceed past.",
            "tags": ["decisions"],
            "timestamp": _now(),
            "path": {"decisions": rows},
        },
        body="\n" + body,
    )


def infer_doc_type(path: Path, root: Path) -> str:
    parent = path.parent.name
    if parent in DOC_TYPE_BY_DIR:
        return DOC_TYPE_BY_DIR[parent]
    return "Document"


def add_frontmatter(path: Path, root: Path, report: Report) -> okf.Doc | None:
    """Give a legacy document OKF frontmatter, deriving what can be derived."""
    text = path.read_text(encoding="utf-8")
    if okf.split(text)[0] is not None:
        return None  # already has frontmatter

    doc_type = infer_doc_type(path, root)
    heading = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    title = heading.group(1) if heading else path.stem.replace("-", " ")
    title = re.sub(r"^(Path|LCG|LCM)\s*[—–-]\s*", "", title).strip()

    meta = {"type": doc_type, "title": title, "description": "", "tags": [], "timestamp": _now()}

    if doc_type == "Build Log Entry":
        stamp = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
        label = re.search(
            r"\b(DECISION|PROBLEM|RESOLUTION|CHANGE|RETROSPECTIVE|SESSION-CLOSE)\b", text
        )
        block = {}
        if stamp:
            block["date"] = stamp.group(1)
        if label:
            block["entry_type"] = label.group(1)
        else:
            report.warn(f"{path.name}: no build log entry type label found")
        related = sorted({f"T-{n}" for n in re.findall(r"\bWO-(\d{3,})\b", text)})
        if related:
            block["related_tasks"] = related
        if block:
            meta["path"] = block

    return okf.Doc(path=path, meta=meta, body="\n" + text.lstrip("\n"))


CLAUDE_SHIM = """# CLAUDE.md

This project's instructions live in [AGENTS.md](AGENTS.md). Read that file.

This shim exists only because some tools look for a file by this name. It is
deliberately empty of content: anything written here would be a second copy of
something, and a second copy is a thing that drifts.
"""

PROFILE_POINTER = """
## Global Profile

If `$LCP_HOME` is set, read `$LCP_HOME/profile/index.md` (or run `path profile`) for the
project owner's working preferences. **Anything in this repository overrides it.**

Standing order: when you learn something true of the project owner, not this project —
a working preference, a stack default, a personal convention — persist it immediately
with `path profile add <doc> "<text>"` (`doc`: identity, working-style, conventions, or
stack). Never hand-edit the profile files.
"""

AVAILABLE_COMMANDS = """## Available Commands

Path is a single command on `$PATH`. This project contains no Path code — there is one
copy of the tool, so there is nothing here to drift out of date.

```bash
path status                  # project status and task queue
path check [T-NNN]           # proof of done: validate a task, or the whole project
path metrics                 # burn-up, volatility, drift — read from frontmatter
path new task "<title>" --effort N
path task start|block|complete T-NNN
path log change|drift|issue T-NNN "<note>"
path close                   # session-close entry, then regenerate status.html
```
"""


def convert_agents_md(root: Path, report: Report, apply: bool) -> None:
    """CLAUDE.md becomes AGENTS.md, and CLAUDE.md becomes a pointer to it.

    The canonical file is named for no vendor because Path must work with any
    tool (F-02, NF-19). The shim left behind carries no content of its own, so
    there is nothing in it that can drift out of step with the real file.
    """
    project = okf.project_dir(root)
    claude, agents = project / "CLAUDE.md", project / "AGENTS.md"

    if agents.is_file():
        report.note("AGENTS.md already exists; left alone")
        return
    if not claude.is_file():
        report.warn("no CLAUDE.md found, so no AGENTS.md was created — write one by hand (F-02)")
        return

    text = claude.read_text(encoding="utf-8")

    # The navigation guide is prose for an agent to read, so the vocabulary in
    # it is instructions rather than a historical record: it should say what
    # the system is called now.
    text = LEGACY_PATH_PREFIX_RE.sub(".path/", text)
    text = re.sub(r"\bWO-(\d{3,})-([A-Za-z0-9_-]*)\.md\b", r"T-\1-\2.md", text)
    text = re.sub(r"\bWO-(\d{3,})\b", r"T-\1", text)
    text = text.replace("work-orders/", "tasks/").replace("WO-TEMPLATE.md", "TASK-TEMPLATE.md")
    # Case-insensitive, preserving the case that was there. Spelling out the
    # variants by hand missed "Work order" — sentence case, which is exactly how
    # it appears in a nav table — and left "Work order template" behind.
    def _retitle(match: re.Match) -> str:
        word, plural = match.group(1), match.group(2) or ""
        replacement = "task" + ("s" if plural else "")
        if word[0].isupper():
            replacement = replacement.capitalize()
        return replacement

    text = re.sub(r"\b([Ww]ork[ -][Oo]rder)(s)?\b", _retitle, text)
    text = re.sub(r"^#\s*CLAUDE\.md\s*$", "# AGENTS.md", text, flags=re.MULTILINE)

    # The old Available Commands section tells the reader to run scripts this
    # migration just deleted. Leaving it would put broken instructions in the
    # first file every agent reads.
    replaced = re.sub(
        r"^## Available Commands\s*$.*?(?=^## |\Z)", AVAILABLE_COMMANDS, text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if replaced != text:
        report.note("AGENTS.md: Available Commands now points at the CLI, not deleted scripts")
        text = replaced

    if "$LCP_HOME" not in text:
        text = text.rstrip("\n") + "\n" + PROFILE_POINTER

    report.renames.append(("CLAUDE.md", "AGENTS.md"))
    report.note("CLAUDE.md is now a pointer to AGENTS.md")
    if apply:
        agents.write_text(text, encoding="utf-8")
        claude.write_text(CLAUDE_SHIM, encoding="utf-8")


BUILD_LOG_WO_RE = re.compile(r"\bwo-(\d{3,})\b")


def rename_build_log_files(root: Path, report: Report, apply: bool) -> dict[str, str]:
    """Rename build-log files whose slug still says wo-NNN.

    Task filenames are `WO-NNN-slug.md` — uppercase, structured, matched by
    `rewrite_references` below. Build-log filenames follow a different
    convention entirely: `[YYYY-MM-DD]-[topic].md`, lowercase-hyphenated, and a
    topic that happens to be about a work order writes it lowercase —
    `2026-06-27-wo-001-retrospective.md`. That pattern shares nothing with the
    uppercase one, so it was never touched: a project could finish migrating
    with task T-001 sitting next to a retrospective still named after WO-001.

    Returns `{old_basename: new_basename}` for every file renamed, which
    `rewrite_build_log_references` then uses to fix every pointer to them.
    """
    build_log = root / "build-log"
    if not build_log.is_dir():
        return {}

    renames: dict[str, str] = {}
    for path in sorted(build_log.glob("*.md")):
        if okf.is_reserved(path):
            continue
        new_name = BUILD_LOG_WO_RE.sub(r"t-\1", path.name)
        if new_name != path.name:
            renames[path.name] = new_name

    if not renames:
        return {}

    for old_name, new_name in renames.items():
        report.renames.append((f"build-log/{old_name}", f"build-log/{new_name}"))
    if apply:
        for old_name, new_name in renames.items():
            (build_log / old_name).rename(build_log / new_name)

    return renames


def rewrite_build_log_references(root: Path, renames: dict[str, str], apply: bool) -> int:
    """Fix every pointer to a build-log file this run renamed.

    This is different from the WO-009-in-a-commit-message case in
    `rewrite_references`: that was a quotation of something someone else said,
    and rewriting it would put words in a commit's mouth it never spoke. A
    mention of a build-log filename — whether a markdown link or a bare
    backtick-quoted name in a sentence — is not a quotation of anything; it is
    a pointer to a file Path itself is renaming, and Path already treats a
    stale pointer as a defect (`path check` fails a broken link for the same
    reason). Both forms get fixed here, since only the link form is inside
    something `check` can see and verify.

    A literal string replace rather than a regex: every filename here is
    specific enough that a substring match cannot collide with anything else,
    and it sidesteps escaping the dots and hyphens a regex would need.
    """
    if not renames:
        return 0

    targets: list[Path] = []
    for directory in ("tasks", "requirements", "blueprints", "build-log"):
        if (root / directory).is_dir():
            targets.extend(sorted((root / directory).glob("*.md")))
    project = okf.project_dir(root)
    for extra in (root / "decisions-log.md", project / "AGENTS.md", project / "CLAUDE.md"):
        if extra.is_file():
            targets.append(extra)

    changed = 0
    for path in targets:
        text = original = path.read_text(encoding="utf-8")
        for old_name, new_name in renames.items():
            text = text.replace(old_name, new_name)
        if text != original:
            changed += 1
            if apply:
                path.write_text(text, encoding="utf-8")
    return changed


def rewrite_references(root: Path, report: Report, apply: bool) -> None:
    """Rewrite references, and only references.

    Filenames and link targets must change or every link breaks, and `path
    check` rightly fails a broken link. Link labels change with them, so a link
    does not announce one id and lead to another.

    A bare `WO-009` in prose is left exactly as written. This is not laziness —
    an lcg drift entry reads:

        Commit `2e54386` ("WO-009 complete; alpha ready") silently bumped ...

    That is a quotation of a real commit message. Rewriting it would make the
    document cite a commit that has never existed, and a record that has been
    tidied to match today's vocabulary is no longer a record. Build log entries
    written before the migration say "work order" because that is what they
    said. `path.migrated_from` carries the old id, so nothing is lost.
    """
    targets: list[Path] = []
    for directory in ("tasks", "requirements", "blueprints", "build-log"):
        if (root / directory).is_dir():
            targets.extend(sorted((root / directory).glob("*.md")))
    project = okf.project_dir(root)
    for extra in (root / "decisions-log.md", project / "AGENTS.md", project / "CLAUDE.md"):
        if extra.is_file():
            targets.append(extra)

    for path in targets:
        text = original = path.read_text(encoding="utf-8")
        # A bare `path/` prefix predating the dotfile convention: a navigation
        # pointer, not a quotation, so unlike a bare WO-009 mention it is
        # rewritten the same as any other link or filename below.
        text = LEGACY_PATH_PREFIX_RE.sub(".path/", text)
        # Filenames, wherever they appear — including inside link targets.
        text = re.sub(r"\bWO-(\d{3,})-([A-Za-z0-9_-]*)\.md\b", r"T-\1-\2.md", text)
        # Link labels, so a link does not say one id and lead to another.
        text = re.sub(r"\[WO-(\d{3,})\]", r"[T-\1]", text)
        text = text.replace("work-orders/", "tasks/")
        text = text.replace("WO-TEMPLATE.md", "TASK-TEMPLATE.md")
        if text != original:
            changed = sum(1 for a, b in zip(original.splitlines(), text.splitlines()) if a != b)
            report.rewrites.append((str(_rel(path, root)), changed))
            if apply:
                path.write_text(text, encoding="utf-8")


def migrate(
    project: Path,
    estimates: dict[str, int] | None = None,
    apply: bool = False,
) -> Report:
    report = Report()
    estimates = estimates or {}

    root = okf.find_project_root(project)
    if root is None:
        raise MigrationError(f"no Path project found at {project}")

    repo = repo_root(root)
    # A dry run writes nothing, so a dirty tree cannot hurt it — and a dirty
    # tree is exactly when someone wants to see what migration would do before
    # deciding how to clean up. Only --apply needs the guard.
    if apply:
        require_clean_tree(repo)

    wo_dir = root / "work-orders"
    if not wo_dir.is_dir():
        raise MigrationError(f"{wo_dir} does not exist; is this project already migrated?")

    tasks_dir = root / "tasks"
    work_orders = sorted(p for p in wo_dir.glob("WO-*.md") if "TEMPLATE" not in p.name)
    if not work_orders:
        raise MigrationError(f"no work orders found in {wo_dir}")

    # 1. Convert every work order before writing anything, so a parse failure
    #    on the last file does not leave the project half-migrated.
    converted = [convert_work_order(repo, root, p, estimates, report) for p in work_orders]
    report.work_orders = len(converted)

    if apply:
        tasks_dir.mkdir(exist_ok=True)

    for old_path, doc in converted:
        report.renames.append(
            (_rel(old_path, root), _rel(doc.path, root))
        )
        if apply:
            okf.save(doc)
            _git(repo, "rm", "-q", "--cached", str(old_path.relative_to(repo)))
            old_path.unlink()
            _git(repo, "add", str(doc.path.relative_to(repo)))

    # 2. The template.
    canonical_template = Path(__file__).resolve().parent.parent / "tasks" / "TASK-TEMPLATE.md"
    report.renames.append(("work-orders/WO-TEMPLATE.md", "tasks/TASK-TEMPLATE.md"))
    if apply:
        shutil.copy(canonical_template, tasks_dir / "TASK-TEMPLATE.md")
        old_template = wo_dir / "WO-TEMPLATE.md"
        if old_template.is_file():
            old_template.unlink()
        # Leave nothing behind that looks like it still holds work.
        remaining = list(wo_dir.iterdir())
        if remaining:
            report.warn(
                f"work-orders/ still holds {len(remaining)} unexpected file(s); left in place: "
                + ", ".join(p.name for p in remaining[:5])
            )
        else:
            wo_dir.rmdir()

    # 3. Frontmatter for everything else.
    for directory in ("requirements", "blueprints", "build-log"):
        target = root / directory
        if not target.is_dir():
            continue
        for path in sorted(target.glob("*.md")):
            if okf.is_reserved(path):
                continue
            doc = add_frontmatter(path, root, report)
            if doc:
                report.frontmatter_added.append(str(_rel(path, root)))
                if apply:
                    okf.save(doc)

    # 4. The decisions log.
    decisions_doc = convert_decisions(root, report)
    if decisions_doc and apply:
        okf.save(decisions_doc)

    # 5. The entry document, references throughout, then the build-log
    #    filenames rewrite_references' pattern doesn't reach.
    convert_agents_md(root, report, apply)
    rewrite_references(root, report, apply)
    build_log_renames = rename_build_log_files(root, report, apply)
    rewrite_build_log_references(root, build_log_renames, apply)

    # 6. Indexes.
    if apply:
        # Derived from what is now on disk rather than from `converted`, so
        # migration and every later mutation produce one identical shape.
        okf.rebuild_tasks_index(tasks_dir, okf.project_dir(root).name, apply)
        build_log = root / "build-log"
        if build_log.is_dir():
            okf.rebuild_build_log_index(build_log, okf.project_dir(root).name, apply)

    # 7. Per-project Path code goes away; the CLI replaces it.
    project = okf.project_dir(root)
    for target in (root / "scripts", project / ".claude" / "commands" / "path.md"):
        if target.exists():
            report.deleted.append(_rel(target, root))
            if apply:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

    if apply:
        # Scoped to the whole project, not just root (".path/"), because
        # AGENTS.md, CLAUDE.md, and .claude/ live at the project's top level in
        # the nested layout. Scoped to the project rather than the whole repo,
        # because lcm is a monorepo and an unrelated Dart change sitting in the
        # working tree must not get swept into this commit.
        _git(repo, "add", "-A", str(project.relative_to(repo)))

    return report


def format_report(report: Report, apply: bool) -> str:
    lines = []
    verb = "Migrated" if apply else "Would migrate"
    lines.append(f"{verb} {report.work_orders} work orders to tasks.")
    lines.append("")

    lines.append(f"Renames ({len(report.renames)}):")
    for old, new in report.renames[:6]:
        lines.append(f"  {old}  ->  {new}")
    if len(report.renames) > 6:
        lines.append(f"  ... and {len(report.renames) - 6} more")

    if report.frontmatter_added:
        lines.append("")
        lines.append(f"Frontmatter added ({len(report.frontmatter_added)}):")
        for name in report.frontmatter_added[:6]:
            lines.append(f"  {name}")
        if len(report.frontmatter_added) > 6:
            lines.append(f"  ... and {len(report.frontmatter_added) - 6} more")

    if report.rewrites:
        total = sum(n for _, n in report.rewrites)
        lines.append("")
        lines.append(f"Reference rewrites: {total} lines across {len(report.rewrites)} files")

    lines.append("")
    lines.append(f"Decisions migrated: {report.decisions_migrated}")

    if report.deleted:
        lines.append("")
        lines.append("Deleted (the CLI replaces these):")
        for name in report.deleted:
            lines.append(f"  {name}")

    if report.notes:
        lines.append("")
        lines.append("Notes:")
        for note in report.notes:
            lines.append(f"  {note}")

    if report.warnings:
        lines.append("")
        lines.append(f"Warnings ({len(report.warnings)}) — reported, not guessed:")
        for warning in report.warnings[:12]:
            lines.append(f"  {warning}")
        if len(report.warnings) > 12:
            lines.append(f"  ... and {len(report.warnings) - 12} more")

    return "\n".join(lines)


def load_estimates(path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = {k: v for k, v in data.items() if not tasks_mod.is_fibonacci(v)}
    if bad:
        raise MigrationError(
            f"estimates that are not Fibonacci numbers: {bad}\n"
            "The scale is 1, 2, 3, 5, 8, 13, 21, 34, ... with no upper bound."
        )
    return data


__all__ = ["migrate", "format_report", "load_estimates", "MigrationError", "Report"]
