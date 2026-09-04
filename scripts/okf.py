"""OKF concept documents: read, write, and round-trip without damage.

Implements the file-level contract described in blueprints/06-okf-mapping.md.

Two rules from the OKF specification drive the design here:

    Producers may add custom key-value pairs; consumers must preserve unknown
    keys.

    index.md and log.md are reserved filenames and cannot be concept documents.

Everything else in this module exists to keep a rewrite from changing bytes it
was not asked to change.

The one import that looks upside-down is `next`. It holds the pure derivations
over frontmatter rows — readiness, ranking, batch progress — and imports nothing
itself, so it is a leaf rather than a layer above this one. `rebuild_tasks_index`
needs those derivations, and the alternative was a second copy of them here.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import next as next_mod

try:
    import yaml
except ImportError:  # pragma: no cover - environment problem, not logic
    sys.exit(
        "Path requires PyYAML.\n"
        "Install it with one of:\n"
        "  uv pip install pyyaml\n"
        "  python3 -m pip install --user pyyaml\n"
        "Then re-run. `path doctor` will confirm."
    )

RESERVED_NAMES = {"index.md", "log.md"}

# Consumes through the newline that ends the closing `---` line, so the body
# begins at the next byte. Anything else loses a blank line on the first write.
FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)

# Strings that look like a date or an ISO 8601 datetime. Used to decide what may
# be emitted unquoted; see _StableDumper.
_DATEISH_RE = re.compile(
    r"\A\d{4}-\d{2}-\d{2}"          # 2026-07-16
    r"(?:[T ]\d{2}:\d{2}:\d{2}"     # T10:00:00
    r"(?:\.\d+)?"                   # .123
    r"(?:Z|[+-]\d{2}:?\d{2})?)?\Z"  # Z or +01:00
)


class OKFError(Exception):
    """A document violates the OKF contract."""


class _StableLoader(yaml.SafeLoader):
    """SafeLoader that leaves dates alone.

    PyYAML resolves an unquoted `2026-07-16T10:00:00Z` to a datetime, and
    re-emitting that datetime produces `2026-07-16 10:00:00+00:00` — the `T`
    and `Z` are silently destroyed. Since Path rewrites frontmatter whenever it
    appends a log entry, that would reformat timestamps on every touch and
    churn the diff of files nobody edited.

    Dropping the implicit timestamp resolver keeps dates as strings, so they
    round-trip byte-for-byte. Path treats them as opaque and parses explicitly
    where it needs real dates.
    """


_StableLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in _StableLoader.yaml_implicit_resolvers.items()
}


class _StableDumper(yaml.SafeDumper):
    """SafeDumper that emits date-like strings unquoted.

    The dumper needs the timestamp resolver dropped as well as the loader. With
    it in place the emitter sees that a plain `2026-07-16` would resolve to a
    timestamp rather than the str it is holding, and quotes it defensively —
    producing `created: '2026-07-16'`, which is correct YAML but unlike every
    other OKF bundle in the world.
    """


_StableDumper.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in _StableDumper.yaml_implicit_resolvers.items()
}


def _represent_list(dumper: yaml.Dumper, data: list) -> yaml.Node:
    # A list of plain scalars reads better inline — `tags: [okf, schema]` — and
    # that is the form the OKF specification's own examples use. Lists holding
    # mappings (drift_log, decisions) stay block style, where they are legible.
    inline = all(isinstance(item, (str, int, float, bool)) for item in data)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=inline)


_StableDumper.add_representer(list, _represent_list)


@dataclass
class Doc:
    """An OKF concept document: frontmatter plus a Markdown body."""

    path: Path
    meta: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @property
    def type(self) -> str | None:
        return self.meta.get("type")

    @property
    def path_meta(self) -> dict[str, Any]:
        """The `path:` extension mapping, created on access if absent."""
        block = self.meta.setdefault("path", {})
        if not isinstance(block, dict):
            raise OKFError(f"{self.path}: `path:` must be a mapping, got {type(block).__name__}")
        return block


def is_reserved(path: Path) -> bool:
    """True for OKF's reserved filenames, which carry no frontmatter."""
    return path.name in RESERVED_NAMES


def split(text: str) -> tuple[str | None, str]:
    """Split raw text into (frontmatter_text, body). Frontmatter is None if absent."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    return match.group(1), text[match.end():]


def loads(text: str, source: Path | str = "<string>") -> Doc:
    frontmatter, body = split(text)
    path = Path(source) if not isinstance(source, Path) else source

    if frontmatter is None:
        raise OKFError(f"{source}: no YAML frontmatter (OKF conformance rule 1)")

    try:
        meta = yaml.load(frontmatter, Loader=_StableLoader)
    except yaml.YAMLError as exc:
        raise OKFError(f"{source}: frontmatter is not parseable YAML: {exc}") from exc

    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise OKFError(f"{source}: frontmatter must be a mapping, got {type(meta).__name__}")

    return Doc(path=path, meta=meta, body=body)


def load(path: Path) -> Doc:
    """Read a concept document. Raises OKFError on a reserved file."""
    if is_reserved(path):
        raise OKFError(f"{path}: {path.name} is an OKF reserved file and has no frontmatter")
    return loads(path.read_text(encoding="utf-8"), source=path)


def dumps(doc: Doc) -> str:
    """Serialize a document. Unknown keys and key order are preserved."""
    frontmatter = yaml.dump(
        doc.meta,
        Dumper=_StableDumper,
        sort_keys=False,       # OKF has no canonical order; the author's is as good as any
        allow_unicode=True,
        default_flow_style=False,
        width=100000,          # never wrap a value; wrapping changes the string on reread
    )
    return f"---\n{frontmatter}---\n{doc.body}"


def save(doc: Doc) -> None:
    doc.path.write_text(dumps(doc), encoding="utf-8")


def iter_docs(root: Path, pattern: str = "**/*.md") -> Iterator[Path]:
    """Yield candidate concept paths under root, skipping reserved and hidden files."""
    for path in sorted(root.glob(pattern)):
        if is_reserved(path):
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        yield path


def project_dir(root: Path) -> Path:
    """The project directory containing a documentation root.

    Two layouts, and telling them apart matters: a consumer project nests its
    docs at `<project>/.path/`, so the project is the parent. The Path
    repository is self-hosted with its docs at the top level, so the project
    *is* the root.

    `.path` is an unambiguous signal for which layout this is: only a nested
    docs folder is ever named `.path` — `init_project` and `migrate` are the
    only things that create one, and neither ever creates it for a self-hosted
    root. So the test is just the name, not a `.git` check against the
    product repository's own folder name. That used to matter: the old
    heuristic assumed the Path repository is called `path`, which is only true
    on this machine, by convention, and would misfire the moment anyone forked
    or renamed it. The dotfile-named check has no such assumption baked in.
    """
    if root.name == ".path":
        return root.parent
    return root


def write_index(
    directory: Path,
    title: str,
    entries: list[tuple[str, str]] | None = None,
    apply: bool = True,
    sections: list[tuple[str, list[tuple[str, str]]]] | None = None,
) -> None:
    """Write an OKF-reserved index.md: a directory listing, no frontmatter.

    Lives here rather than with any one caller because it is a general OKF
    fact — "index.md is reserved and frontmatter-free" — not a migration
    detail or an init detail. Both `migrate` and `init` need it and neither
    owns it.

    `sections` groups the listing under headings. OKF describes index.md as a
    directory listing, and the reading taken here is that grouping a listing
    does not stop it being one: every file still appears exactly once, none is
    invented, and no frontmatter claim is introduced. A section with nothing in
    it is omitted rather than written as a bare heading — an empty heading asks
    the reader to notice that nothing is under it.
    """
    lines = [f"# {title}", ""]

    def emit(rows):
        for name, description in rows:
            lines.append(
                f"* [{name}]({name}) - {description}" if description else f"* [{name}]({name})"
            )

    if sections is not None:
        for heading, rows in sections:
            if not rows:
                continue
            lines.append(f"## {heading}")
            lines.append("")
            emit(rows)
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
    else:
        emit(entries or [])

    if apply:
        (directory / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _task_sort_key(name: str) -> tuple[int, str]:
    """Order document filenames by their numeric id, so T-009 precedes T-010.

    Plain filename sort puts T-010 before T-009 the moment ids reach two
    digits, which is exactly when an index stops being readable. The prefix is
    not pinned to `T` because batches are numbered the same way and want the
    same order.
    """
    match = re.match(r"[A-Z]+-(\d+)", name)
    return (int(match.group(1)) if match else 10**9, name)


def rebuild_tasks_index(directory: Path, project_name: str, apply: bool = True) -> list[str]:
    """Rewrite `tasks/index.md`, grouped by what can be started (F-55).

    Returns the names of any files that could not be read, so the caller can
    surface them. A rebuild that silently dropped an unreadable task would
    reproduce the very failure this function exists to remove: an index that
    reads as authoritative while being quietly incomplete.

    The whole file is rewritten rather than appended to, deliberately. An
    append-only index cannot reflect a status change, cannot notice a deleted
    file, and cannot repair itself — which is how these indexes drifted in the
    first place. A full rebuild makes the index a pure function of the
    directory, and that is the only property that keeps it true.

    Grouping is what makes the file worth opening. An identifier-ordered list of
    statuses tells a reader roughly what `ls` would; the point of Path is that
    its documents are readable without its tooling, and "what can I start" is
    the question they were most obviously failing to answer. Readiness and
    ordering come from `next`, the same computation `path status` and
    `path next` use, so the file cannot disagree with the commands.
    """
    if not directory.is_dir():
        return []

    unreadable: list[str] = []
    task_rows: list[dict] = []
    batch_rows: list[dict] = []

    for path in sorted(directory.glob("[TB]-*.md"), key=lambda p: _task_sort_key(p.name)):
        if is_reserved(path):
            continue
        try:
            doc = load(path)
            meta = dict(doc.path_meta)
        except (OKFError, yaml.YAMLError, OSError):
            unreadable.append(path.name)
            continue
        meta["_name"] = path.name
        meta["_title"] = doc.meta.get("title") or path.stem
        (batch_rows if doc.type == "Batch" else task_rows).append(meta)

    sections = _task_index_sections(task_rows, batch_rows)
    write_index(directory, f"{project_name} — Tasks", apply=apply, sections=sections)
    return unreadable


def _task_index_sections(
    task_rows: list[dict], batch_rows: list[dict]
) -> list[tuple[str, list[tuple[str, str]]]]:
    """The grouped listing, as (heading, entries) pairs."""
    rollups = [next_mod.rollup(task_rows, batch) for batch in batch_rows]
    by_id = {str(b.get("id")): b for b in batch_rows}
    ready = next_mod.readiness(task_rows, rollups)
    name_of = {str(r.get("id")): r["_name"] for r in task_rows}

    def batch_line(roll):
        row = by_id[roll["id"]]
        return (
            row["_name"],
            f"{roll['status']} · {roll['tasks_done']}/{roll['tasks_total']} tasks, "
            f"{roll['points_done']}/{roll['points_total']} pts — {roll['title']}",
        )

    def task_line(entry, note=""):
        bits = [f"{entry['effort']} pts" if isinstance(entry.get("effort"), int) else "no estimate"]
        if entry["batch"]:
            bits.append(str(entry["batch"]))
        if note:
            bits.append(note)
        return (name_of[entry["id"]], " · ".join(bits) + f" — {entry['title']}")

    return [
        ("Batches", [batch_line(r) for r in rollups if r["status"] != "complete"]),
        (
            "Ready now",
            [
                task_line(e, f"unblocks {e['unblocks']}" if e["unblocks"] else "")
                for e in ready["ready"]
            ],
        ),
        ("In progress", [task_line(e) for e in ready["in_progress"]]),
        (
            "Waiting on prerequisites",
            [task_line(e, f"needs {', '.join(e['needs'])}") for e in ready["waiting"]],
        ),
        ("Blocked", [task_line(e) for e in ready["blocked"]]),
        ("Complete", [task_line(e) for e in ready["complete"]]),
        ("Completed batches", [batch_line(r) for r in rollups if r["status"] == "complete"]),
    ]


def rebuild_build_log_index(directory: Path, project_name: str, apply: bool = True) -> list[str]:
    """Rewrite `build-log/index.md` from the frontmatter on disk.

    Build-log filenames lead with their date, so filename order is already
    chronological and needs no special key. Entries are described by type and
    title for the same reason tasks are: a list of bare filenames tells a
    reader nothing `ls` would not.
    """
    if not directory.is_dir():
        return []

    entries: list[tuple[str, str]] = []
    unreadable: list[str] = []
    for path in sorted(directory.glob("*.md")):
        if is_reserved(path):
            continue
        try:
            doc = load(path)
            entry_type = doc.path_meta.get("entry_type") or "ENTRY"
            title = doc.meta.get("title") or path.stem
        except (OKFError, yaml.YAMLError, OSError):
            unreadable.append(path.name)
            continue
        entries.append((path.name, f"{entry_type} — {title}"))

    write_index(directory, f"{project_name} — Build Log", entries, apply)
    return unreadable


def find_project_root(start: Path | None = None) -> Path | None:
    """Locate the Path documentation root for a project.

    Two layouts are supported. A consumer project nests its documentation
    under `.path/` — a dotfile, deliberately, matching the convention every
    other meta/tooling directory uses (`.git`, `.github`, `.vscode`) so that
    Path's own folder reads as tooling rather than as project content, and
    can never collide with something a project's own source tree wants to
    name `path`. The Path repository itself is self-hosted at the top level,
    since a `.path/path/` directory would be its own kind of joke.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        nested = candidate / ".path"
        if nested.is_dir() and (nested / "blueprints").is_dir():
            return nested
        if (candidate / "blueprints").is_dir() and (candidate / "requirements").is_dir():
            return candidate
        if (candidate / ".git").exists():
            break  # stop at the repo boundary rather than wandering up to $HOME
    return None
