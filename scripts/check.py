"""Proof of done: mechanically verify a completion claim.

Implements F-40 through F-42. Every check here answers a question of fact, not
of judgment — whether a date is consistent, whether a link resolves, whether a
retrospective was actually written. Nothing in this module has an opinion about
whether the work was any good; that is what a human review is for.

The point is that an executor's claim to have finished is checkable rather than
trusted. `path check` exits non-zero when it isn't true.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import okf
from tasks import is_fibonacci

VALID_STATUSES = ("pending", "in-progress", "complete", "blocked")
TASK_ID_RE = re.compile(r"\AT-\d{3}\Z")
TASK_FILENAME_RE = re.compile(r"\A(T-\d{3})-[a-z0-9-]+\.md\Z")
BATCH_ID_RE = re.compile(r"\AB-\d{3}\Z")
BATCH_FILENAME_RE = re.compile(r"\A(B-\d{3})-[a-z0-9-]+\.md\Z")
REQUIREMENT_ID_RE = re.compile(r"\A(?:F|NF)-\d{2,}\Z")
DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
LINK_RE = re.compile(r"\[[^\]]*\]\((?!https?:|mailto:)([^)#]+)(?:#[^)]*)?\)")

# Deliberately narrow. A bare `\bTODO\b` fires on documents that merely discuss
# TODOs — lcm's T-001 has the acceptance criterion "No `TODO`, `FIXME`, or
# placeholder comments in committed code", and T-045 describes bare-TODO
# detection. Both are correct prose, and a check that fails them teaches people
# to ignore it. A real leftover marker is followed by a colon or fills a
# template blank; a missed marker costs less than a check nobody trusts.
PLACEHOLDER_RE = re.compile(
    r"(?:^|\s)(?:TODO|FIXME|XXX|TBD)\s*:"          # TODO: finish this
    r"|\[NNN\]|\[Short Descriptive Title\]"        # untouched template blanks
    r"|\[One paragraph\."
    r"|\[Task \d+ —"
    r"|\[Criterion \d+ —"
)

CODE_SPAN_RE = re.compile(r"`[^`\n]*`|```.*?```", re.DOTALL)
UNCHECKED_BOX_RE = re.compile(r"^-\s*\[ \]", re.MULTILINE)

# Deliberately conservative. A high-entropy string is a guess; these are the
# shapes that are unambiguous enough to stop a commit over. NF-23 makes this a
# backstop against the profile/project separation failing, not a scanner.
SECRET_PATTERNS = (
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "GitHub token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"), "OpenAI-style API key"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"), "Anthropic API key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
     "hardcoded credential"),
)


@dataclass
class Finding:
    """One thing that is wrong. `level` is fail or warn; only fail sets the exit code."""

    level: str
    where: str
    message: str

    def __str__(self) -> str:
        mark = "FAIL" if self.level == "fail" else "warn"
        return f"  [{mark}] {self.where}: {self.message}"


class Checker:
    def __init__(self, root: Path):
        self.root = root
        self.findings: list[Finding] = []

    # -- reporting ---------------------------------------------------------

    def fail(self, where: str, message: str) -> None:
        self.findings.append(Finding("fail", where, message))

    def warn(self, where: str, message: str) -> None:
        self.findings.append(Finding("warn", where, message))

    @property
    def failed(self) -> bool:
        return any(f.level == "fail" for f in self.findings)

    # -- helpers -----------------------------------------------------------

    def tasks_dir(self) -> Path:
        return self.root / "tasks"

    def task_paths(self) -> list[Path]:
        directory = self.tasks_dir()
        if not directory.is_dir():
            return []
        return sorted(p for p in directory.glob("T-*.md") if not okf.is_reserved(p))

    def batch_paths(self) -> list[Path]:
        directory = self.tasks_dir()
        if not directory.is_dir():
            return []
        return sorted(p for p in directory.glob("B-*.md") if not okf.is_reserved(p))

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(okf.project_dir(self.root)))
        except ValueError:
            return str(path)

    def _requirement_ids(self) -> set[str]:
        ids: set[str] = set()
        directory = self.root / "requirements"
        if not directory.is_dir():
            return ids
        for path in directory.glob("*.md"):
            ids.update(re.findall(r"\*\*((?:F|NF)-\d{2,})\*\*", path.read_text(encoding="utf-8")))
        return ids

    def _agents_file(self) -> Path | None:
        for candidate in (okf.project_dir(self.root) / "AGENTS.md", self.root / "AGENTS.md"):
            if candidate.is_file():
                return candidate
        return None

    # -- document-level checks --------------------------------------------

    def check_document(self, path: Path) -> okf.Doc | None:
        """OKF conformance rules 1 and 2, plus links and hygiene."""
        where = self.rel(path)
        try:
            doc = okf.load(path)
        except okf.OKFError as exc:
            self.fail(where, str(exc).split(": ", 1)[-1])
            return None

        if not doc.type:
            self.fail(where, "frontmatter has no non-empty `type` (OKF conformance rule 2)")

        self.check_links(path, doc)
        self.check_secrets(path, doc)
        return doc

    def check_links(self, path: Path, doc: okf.Doc) -> None:
        """OKF tolerates broken links. Path does not — see blueprints/03-conventions.md."""
        for link in LINK_RE.findall(doc.body):
            target = (path.parent / link.strip()).resolve()
            if not target.exists():
                self.fail(self.rel(path), f"broken link: {link}")

    def check_secrets(self, path: Path, doc: okf.Doc) -> None:
        text = okf.dumps(doc)
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                self.fail(self.rel(path), f"possible {label} committed (NF-14)")

    # -- task checks -------------------------------------------------------

    def check_task(
        self,
        path: Path,
        requirement_ids: set[str],
        all_tasks: dict[str, dict],
        all_batches: dict[str, dict] | None = None,
    ) -> None:
        where = self.rel(path)
        doc = self.check_document(path)
        if doc is None:
            return

        if doc.type != "Task":
            self.fail(where, f"type is {doc.type!r}, expected 'Task'")

        try:
            meta = doc.path_meta
        except okf.OKFError as exc:
            self.fail(where, str(exc).split(": ", 1)[-1])
            return

        # id matches filename
        filename_match = TASK_FILENAME_RE.match(path.name)
        if not filename_match:
            self.fail(where, f"filename must match T-NNN-slug.md, got {path.name!r}")
        task_id = meta.get("id")
        if not task_id or not TASK_ID_RE.match(str(task_id)):
            self.fail(where, f"path.id must be T-NNN, got {task_id!r}")
        elif filename_match and filename_match.group(1) != task_id:
            self.fail(where, f"path.id {task_id!r} does not match filename {path.name!r}")

        # status
        status = meta.get("status")
        if status not in VALID_STATUSES:
            self.fail(where, f"path.status must be one of {', '.join(VALID_STATUSES)}, got {status!r}")

        # effort
        effort = meta.get("effort")
        if not is_fibonacci(effort):
            self.fail(
                where,
                f"path.effort must be a Fibonacci number (1, 2, 3, 5, 8, 13, 21, ...), "
                f"got {effort!r}",
            )

        self.check_task_dates(where, meta, status)
        self.check_task_links(where, meta, requirement_ids, all_tasks)
        self.check_task_batch(where, meta, all_batches)

        if status == "complete":
            self.check_retrospective(where, str(task_id))
            self.check_checkboxes(where, doc)

        self.check_body_has_no_log_sections(where, doc)

        # Code spans go first: a marker quoted as an example is not a leftover.
        prose = CODE_SPAN_RE.sub("", doc.body)
        found = PLACEHOLDER_RE.search(prose)
        if found:
            self.fail(where, f"placeholder {found.group(0).strip()!r} left in the body")

    def check_task_dates(self, where: str, meta: dict, status: str | None) -> None:
        for field in ("created", "updated"):
            value = meta.get(field)
            if not value:
                self.fail(where, f"path.{field} is required")
            elif not DATE_RE.match(str(value)):
                self.fail(where, f"path.{field} must be YYYY-MM-DD, got {value!r}")

        completed = meta.get("completed")

        # The iff that keeps burn-up honest: a completed date with no complete
        # status (or the reverse) means the chart is plotting a fiction.
        if status == "complete" and not completed:
            self.fail(where, "status is complete but path.completed is empty")
        if status != "complete" and completed:
            self.fail(where, f"path.completed is set to {completed!r} but status is {status!r}")

        if completed and not DATE_RE.match(str(completed)):
            self.fail(where, f"path.completed must be YYYY-MM-DD, got {completed!r}")

        created, updated = meta.get("created"), meta.get("updated")
        if _is_date(created) and _is_date(updated) and _parse(updated) < _parse(created):
            self.fail(where, f"path.updated ({updated}) is before path.created ({created})")
        if _is_date(created) and _is_date(completed) and _parse(completed) < _parse(created):
            self.fail(where, f"path.completed ({completed}) is before path.created ({created})")

    def check_task_links(
        self, where: str, meta: dict, requirement_ids: set[str], all_tasks: dict[str, dict]
    ) -> None:
        for req in meta.get("implements") or []:
            if not REQUIREMENT_ID_RE.match(str(req)):
                self.fail(where, f"path.implements: {req!r} is not a requirement id")
            elif requirement_ids and str(req) not in requirement_ids:
                self.fail(where, f"path.implements: {req} does not exist in requirements/")

        for prerequisite in meta.get("requires") or []:
            other = all_tasks.get(str(prerequisite))
            if other is None:
                self.fail(where, f"path.requires: {prerequisite} does not exist")
            elif meta.get("status") == "complete" and other.get("status") != "complete":
                self.fail(
                    where,
                    f"path.requires: {prerequisite} is {other.get('status')!r}, "
                    "but this task is complete",
                )

    def check_task_batch(self, where: str, meta: dict, all_batches: dict[str, dict] | None) -> None:
        """F-54: a task belongs to at most one batch, and to one that exists.

        Absent and null are both fine and both mean the same thing — most tasks
        are not batched, and that has to stay the cheap, silent default rather
        than something a task has to declare.
        """
        batch_id = meta.get("batch")
        if batch_id in (None, ""):
            return
        if not BATCH_ID_RE.match(str(batch_id)):
            self.fail(where, f"path.batch must be B-NNN, got {batch_id!r}")
        elif all_batches is not None and str(batch_id) not in all_batches:
            self.fail(where, f"path.batch: {batch_id} does not exist")

    def check_batch(self, path: Path, all_tasks: dict[str, dict]) -> None:
        """F-53, F-54: a batch document, and the sequence-membership agreement.

        The agreement is the load-bearing check. Membership is recorded on the
        task and order on the batch, which is two files describing one set. The
        commands keep them together; this is what makes it impossible to commit
        them apart, and without it the split would be a straightforward way to
        lose a task out of every view built from the sequence.
        """
        where = self.rel(path)
        doc = self.check_document(path)
        if doc is None:
            return

        if doc.type != "Batch":
            self.fail(where, f"type is {doc.type!r}, expected 'Batch'")

        try:
            meta = doc.path_meta
        except okf.OKFError as exc:
            self.fail(where, str(exc).split(": ", 1)[-1])
            return

        filename_match = BATCH_FILENAME_RE.match(path.name)
        if not filename_match:
            self.fail(where, f"filename must match B-NNN-slug.md, got {path.name!r}")
        batch_id = meta.get("id")
        if not batch_id or not BATCH_ID_RE.match(str(batch_id)):
            self.fail(where, f"path.id must be B-NNN, got {batch_id!r}")
        elif filename_match and filename_match.group(1) != batch_id:
            self.fail(where, f"path.id {batch_id!r} does not match filename {path.name!r}")

        # F-54 is explicit that these are derived. Finding one on disk means
        # something wrote a value that is only correct until a member moves.
        for forbidden in ("status", "completed"):
            if forbidden in meta:
                self.fail(
                    where,
                    f"path.{forbidden} is derived from the batch's members and must not be stored "
                    "(F-54)",
                )

        self.check_batch_dates(where, meta)

        if batch_id:
            self.check_batch_sequence(where, str(batch_id), meta, all_tasks)

        prose = CODE_SPAN_RE.sub("", doc.body)
        found = PLACEHOLDER_RE.search(prose)
        if found:
            self.fail(where, f"placeholder {found.group(0).strip()!r} left in the body")

    def check_batch_dates(self, where: str, meta: dict) -> None:
        for field_name in ("created", "updated"):
            value = meta.get(field_name)
            if not value:
                self.fail(where, f"path.{field_name} is required")
            elif not DATE_RE.match(str(value)):
                self.fail(where, f"path.{field_name} must be YYYY-MM-DD, got {value!r}")

        created, updated = meta.get("created"), meta.get("updated")
        if _is_date(created) and _is_date(updated) and _parse(updated) < _parse(created):
            self.fail(where, f"path.updated ({updated}) is before path.created ({created})")

    def check_batch_sequence(
        self, where: str, batch_id: str, meta: dict, all_tasks: dict[str, dict]
    ) -> None:
        sequence = meta.get("sequence")
        if sequence is None:
            sequence = []
        if not isinstance(sequence, list):
            self.fail(where, f"path.sequence must be a list, got {sequence!r}")
            return

        listed = [str(t) for t in sequence]
        duplicates = sorted({t for t in listed if listed.count(t) > 1})
        if duplicates:
            self.fail(where, f"path.sequence names {', '.join(duplicates)} more than once")

        for task_id in listed:
            if not TASK_ID_RE.match(task_id):
                self.fail(where, f"path.sequence: {task_id!r} is not a task id")
            elif task_id not in all_tasks:
                self.fail(where, f"path.sequence: {task_id} does not exist")

        claiming = {
            task_id
            for task_id, task_meta in all_tasks.items()
            if str(task_meta.get("batch") or "") == batch_id
        }
        unlisted = sorted(claiming - set(listed))
        if unlisted:
            self.fail(
                where,
                f"path.sequence omits {', '.join(unlisted)}, which claim membership in {batch_id}",
            )
        unclaimed = sorted(
            t for t in set(listed) - claiming if t in all_tasks
        )
        if unclaimed:
            self.fail(
                where,
                f"path.sequence names {', '.join(unclaimed)}, which do not have "
                f"path.batch set to {batch_id}",
            )

    def check_retrospective(self, where: str, task_id: str) -> None:
        """F-41: a completed task must have a RETROSPECTIVE entry that declares it.

        Read from the entry's own frontmatter — ``path.entry_type`` and
        ``path.related_tasks`` — and not from the prose. Matching on the text
        anywhere in the file let a task pass on a name-drop: the sibling project's T-113 was
        checked off against T-110's retrospective, which mentions T-113 only to
        say it is *not* covered there. An entry that means to close a task says so
        in the field built for it."""
        build_log = self.root / "build-log"
        if not build_log.is_dir():
            self.fail(where, "status is complete but there is no build-log/ directory")
            return
        for entry in build_log.glob("*.md"):
            try:
                meta = okf.load(entry).meta.get("path") or {}
            except okf.OKFError:
                continue  # reported by check_document; not this check's business
            if not isinstance(meta, dict):
                continue
            if meta.get("entry_type") != "RETROSPECTIVE":
                continue
            related = meta.get("related_tasks") or []
            if isinstance(related, list) and task_id in [str(t) for t in related]:
                return
        self.fail(
            where,
            f"status is complete but no RETROSPECTIVE build log entry lists {task_id} "
            "in its path.related_tasks",
        )

    def check_checkboxes(self, where: str, doc: okf.Doc) -> None:
        """DoD: "every task in the task list is checked off" and "every
        acceptance criterion is met" are only partially mechanical —
        confirming a box's claim is actually true is judgment, but confirming
        no box was simply left unchecked is a fact. Only checked at
        status: complete; an in-progress task legitimately has open boxes."""
        for heading in ("Tasks", "Acceptance Criteria"):
            section = _section(doc.body, heading)
            if section is None:
                continue
            remaining = len(UNCHECKED_BOX_RE.findall(section))
            if remaining:
                self.fail(
                    where,
                    f"status is complete but '## {heading}' has {remaining} unchecked "
                    f"box{'es' if remaining != 1 else ''} remaining",
                )

    def check_body_has_no_log_sections(self, where: str, doc: okf.Doc) -> None:
        """F-30: one fact, one location. The logs live in frontmatter now."""
        for heading in ("Change Log", "Drift Log", "Issues Found During Execution"):
            if re.search(rf"^##\s+{re.escape(heading)}\s*$", doc.body, re.MULTILINE):
                self.fail(
                    where,
                    f"body still has a '## {heading}' section; that data belongs in "
                    "frontmatter only (F-30)",
                )

    # -- AGENTS.md ---------------------------------------------------------

    def check_agents_md(self) -> None:
        """F-41 / NF-06: the two fields that grow without bound, enforced mechanically."""
        agents = self._agents_file()
        if agents is None:
            self.fail(self.rel(self.root), "no AGENTS.md found (F-02)")
            return

        text = agents.read_text(encoding="utf-8")
        where = self.rel(agents)

        for heading, limit in (("Current Task", 1), ("Project Status", 2)):
            section = _section(text, heading)
            if section is None:
                self.warn(where, f"no '## {heading}' section")
                continue
            lines = [
                line for line in section.splitlines()
                if line.strip() and not line.strip().startswith("*(")
            ]
            if len(lines) > limit:
                self.fail(
                    where,
                    f"'{heading}' is {len(lines)} lines, limit is {limit} — "
                    "move the detail to the build log (see blueprints/03-conventions.md)",
                )


def _section(text: str, heading: str) -> str | None:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return None
    rest = text[match.end():]
    following = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: following.start()] if following else rest


def _is_date(value) -> bool:
    return bool(value) and bool(DATE_RE.match(str(value)))


def _parse(value) -> date:
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def run(
    root: Path,
    task_id: str | None = None,
    write_proof: bool = True,
    batch_id: str | None = None,
) -> tuple[int, list[Finding]]:
    """Check a project, one task within it, or one batch. Returns (exit_code, findings).

    A batch run is the per-task checks over every member plus the batch document
    itself, reported once. It is the same standard applied the same number of
    times — batching the bookkeeping does not batch the scrutiny (F-59).
    """
    checker = Checker(root)
    requirement_ids = checker._requirement_ids()

    # Index every task first: `requires` needs to see tasks other than the one
    # under examination, even when checking a single id.
    all_tasks: dict[str, dict] = {}
    for path in checker.task_paths():
        try:
            doc = okf.load(path)
            meta = doc.meta.get("path") or {}
            if isinstance(meta, dict) and meta.get("id"):
                all_tasks[str(meta["id"])] = meta
        except okf.OKFError:
            continue  # reported properly by check_task below

    all_batches: dict[str, dict] = {}
    for path in checker.batch_paths():
        try:
            meta = okf.load(path).meta.get("path") or {}
            if isinstance(meta, dict) and meta.get("id"):
                all_batches[str(meta["id"])] = meta
        except okf.OKFError:
            continue  # reported properly by check_batch below

    targets = checker.task_paths()
    if task_id:
        targets = [p for p in targets if p.name.startswith(f"{task_id}-")]
        if not targets:
            checker.fail(str(root), f"no task {task_id} in {checker.tasks_dir()}")
    elif batch_id:
        if batch_id not in all_batches:
            checker.fail(str(root), f"no batch {batch_id} in {checker.tasks_dir()}")
        member_ids = {
            str(meta.get("id"))
            for meta in all_tasks.values()
            if str(meta.get("batch") or "") == batch_id
        }
        targets = [
            p for p in targets if p.name.split("-")[0] + "-" + p.name.split("-")[1] in member_ids
        ]
        if not targets and batch_id in all_batches:
            checker.fail(str(root), f"{batch_id} has no members to check")

    for path in targets:
        checker.check_task(path, requirement_ids, all_tasks, all_batches)

    # Checking one task says nothing about a batch, and reporting a sequence
    # disagreement against a file the caller did not ask about would be noise.
    # A whole-project run checks every batch; a batch run checks that batch.
    if not task_id:
        for path in checker.batch_paths():
            if batch_id and not path.name.startswith(f"{batch_id}-"):
                continue
            checker.check_batch(path, all_tasks)

    # Other document types: conformance, links, and secrets only.
    for directory in ("requirements", "blueprints", "build-log", "strategy"):
        target = root / directory
        if target.is_dir():
            for path in okf.iter_docs(target, "*.md"):
                checker.check_document(path)

    decisions = root / "decisions-log.md"
    if decisions.is_file():
        checker.check_document(decisions)

    checker.check_agents_md()

    # Proof is recorded on every member of a passing batch, and on none of a
    # failing one — the same all-or-nothing rule a single task already has.
    if write_proof and (task_id or batch_id) and not checker.failed:
        _record_proof(targets, passed=True)

    return (1 if checker.failed else 0), checker.findings


def _record_proof(paths: list[Path], passed: bool) -> None:
    """F-42: the result is written by the tooling, never by hand."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for path in paths:
        try:
            doc = okf.load(path)
        except okf.OKFError:
            continue
        doc.path_meta["proof"] = {"checked_at": stamp, "result": "pass" if passed else "fail"}
        okf.save(doc)
