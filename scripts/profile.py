"""The global profile: who's using Path, and how they want to work.

Implements F-43 through F-46 and blueprints/07-profile-and-precedence.md.

Two rules shape everything here. Personal content never enters a project — it
reaches an AI tool by reference, never by copy (F-44). And a project's own
documentation always overrides the profile on conflict (F-46) — the profile is
a set of defaults, not a mandate.

This module does not know anything about Kate specifically. The seed files it
writes are templates with instructive placeholders, the same way
tasks/TASK-TEMPLATE.md is a template — not a fabricated biography. Filling them
in is the project owner's job, not this module's.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover — same failure mode as okf.py
    yaml = None

import okf

PROFILE_DOC_ORDER = ("identity.md", "working-style.md", "conventions.md", "stack.md")
PROFILE_DOC_NAMES = tuple(name.removesuffix(".md") for name in PROFILE_DOC_ORDER)

PRECEDENCE_LINE = (
    "These are defaults. Any project's own documentation overrides them on conflict."
)

NOTES_HEADER = "## Notes"

DEFAULT_CONFIG = {
    "project_root": "~/code",
    "graphify": "ask",
    "graphify_min_version": "0.8.0",
    "shims": [],  # populated by install_shims() with whatever it actually detects
}


class ProfileError(Exception):
    """Something about the profile or its home is wrong."""


def home(override: str | None = None) -> Path:
    """`$LCP_HOME`, or the override, or the default. Never assumes it exists."""
    value = override or os.environ.get("LCP_HOME") or "~/.lcp"
    return Path(value).expanduser()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_doc(doc_type_title: str, filename: str, sections: list[str]) -> str:
    """A profile concept document: OKF frontmatter, the precedence line, then
    bracketed prompts for the owner to replace. Mirrors TASK-TEMPLATE.md's
    approach — structure, not invented content."""
    body = "\n\n".join(f"## {s}\n\n[Fill this in.]" for s in sections)
    return (
        "---\n"
        "type: Profile\n"
        f"title: {doc_type_title}\n"
        "description: \n"
        "tags: []\n"
        f"timestamp: {_now()}\n"
        "---\n\n"
        f"# {doc_type_title}\n\n"
        f"*{PRECEDENCE_LINE}*\n\n"
        f"{body}\n"
    )


SEED_DOCS = {
    "identity.md": lambda: _seed_doc(
        "Identity", "identity.md",
        ["Who I am", "My role", "Organisational context"],
    ),
    "working-style.md": lambda: _seed_doc(
        "Working Style", "working-style.md",
        ["How I want an AI to communicate with me", "How much autonomy to default to",
         "What to always ask about before doing"],
    ),
    "conventions.md": lambda: _seed_doc(
        "Personal Conventions", "conventions.md",
        ["Default lint / style preferences", "Default commit message format",
         "Anything I want even when a project doesn't specify it"],
    ),
    "stack.md": lambda: _seed_doc(
        "Stack", "stack.md",
        ["Languages and tools I default to", "Things I actively avoid"],
    ),
}

INDEX_MD = f"""# Global Profile

*{PRECEDENCE_LINE}*

## Documents

* [identity.md](identity.md) - who I am and my role
* [working-style.md](working-style.md) - how I want AI to work with me
* [conventions.md](conventions.md) - personal defaults
* [stack.md](stack.md) - preferred tools and languages
"""


def ensure_scaffold(lcp_home: Path) -> list[Path]:
    """Create `$LCP_HOME`'s structure if it's missing. Never overwrites an
    existing file — a second run only fills in what the first one didn't
    reach, so editing a seed file and re-running is always safe."""
    created: list[Path] = []
    profile_dir = lcp_home / "profile"
    (lcp_home / "state" / "graphify").mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    config_path = lcp_home / "config.yml"
    if not config_path.is_file():
        if yaml is None:
            raise ProfileError("PyYAML is required to write config.yml; see `path doctor`")
        config_path.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False), encoding="utf-8")
        created.append(config_path)

    index_path = profile_dir / "index.md"
    if not index_path.is_file():
        index_path.write_text(INDEX_MD, encoding="utf-8")
        created.append(index_path)

    for name, factory in SEED_DOCS.items():
        path = profile_dir / name
        if not path.is_file():
            path.write_text(factory(), encoding="utf-8")
            created.append(path)

    return created


def load_config(lcp_home: Path) -> dict:
    config_path = lcp_home / "config.yml"
    if not config_path.is_file():
        return dict(DEFAULT_CONFIG)
    if yaml is None:
        raise ProfileError("PyYAML is required to read config.yml; see `path doctor`")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_config(lcp_home: Path, config: dict) -> None:
    if yaml is None:
        raise ProfileError("PyYAML is required to write config.yml; see `path doctor`")
    (lcp_home / "config.yml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def assemble(lcp_home: Path) -> str:
    """Every profile document, concatenated in a stable order, for any tool —
    including one with no configuration system of its own — to consume by
    piping this straight into its context."""
    profile_dir = lcp_home / "profile"
    if not profile_dir.is_dir():
        raise ProfileError(
            f"no profile at {profile_dir}. Run `path profile` once to scaffold it, "
            "then fill in the seed files."
        )

    parts = [f"# Global Profile ({lcp_home})\n\n*{PRECEDENCE_LINE}*\n"]
    for name in PROFILE_DOC_ORDER:
        path = profile_dir / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        # Strip frontmatter for assembly — a consumer wants the content, and
        # the type/tags/timestamp fields are for Path's own tooling, not for
        # an agent's context window.
        body = re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
        parts.append(body.strip())
    return "\n\n---\n\n".join(parts) + "\n"


def add_entry(lcp_home: Path, doc: str, text: str) -> Path:
    """Append a dated, agent-learned fact to a profile document (F-51).

    `doc` is one of `PROFILE_DOC_NAMES`. The entry lands under a `## Notes`
    heading — created on first use, never duplicated — so nothing an owner
    wrote in the document's other sections is ever in the blast radius. The
    document's `timestamp` field is refreshed to record that it changed.
    """
    if doc not in PROFILE_DOC_NAMES:
        raise ProfileError(
            f"{doc!r} is not a profile document. Choose one of: "
            + ", ".join(PROFILE_DOC_NAMES)
        )

    path = lcp_home / "profile" / f"{doc}.md"
    if not path.is_file():
        raise ProfileError(f"no {path} — run `path profile` once to scaffold it")

    concept = okf.load(path)
    concept.meta["timestamp"] = _now()

    if NOTES_HEADER not in concept.body:
        concept.body = concept.body.rstrip("\n") + f"\n\n{NOTES_HEADER}\n"

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    concept.body = concept.body.rstrip("\n") + f"\n- ({date}) {text.strip()}\n"

    okf.save(concept)
    return path


# ── shims ─────────────────────────────────────────────────────────────────────

MARKER_START = "<!-- path:profile:start -->"
MARKER_END = "<!-- path:profile:end -->"


def _managed_block(lcp_home: Path) -> str:
    return (
        f"{MARKER_START}\n"
        "## Little Collie Path — Global Profile\n\n"
        f"If `$LCP_HOME` is set, read `$LCP_HOME/profile/index.md` (or run `path profile`) "
        "for the project owner's working preferences. **Any project's own documentation "
        "overrides this on conflict.**\n\n"
        "Standing order: when you learn something true of the profile's owner, not the "
        "project — a working preference, a stack default, a personal convention — persist "
        "it immediately with `path profile add <doc> \"<text>\"` (`doc`: identity, "
        "working-style, conventions, or stack). Never hand-edit the profile files.\n"
        f"{MARKER_END}"
    )


def _upsert_managed_block(path: Path, lcp_home: Path, apply: bool) -> str:
    """Insert or update a marker-delimited block without touching anything
    else in the file. This is what makes shim writing safe to re-run: existing
    content the owner wrote is never in the blast radius."""
    block = _managed_block(lcp_home)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""

    if MARKER_START in existing and MARKER_END in existing:
        pattern = re.compile(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END), re.DOTALL
        )
        new_text = pattern.sub(block, existing)
        action = "updated" if new_text != existing else "unchanged"
    elif existing.strip():
        new_text = existing.rstrip("\n") + "\n\n" + block + "\n"
        action = "added"
    else:
        new_text = block + "\n"
        action = "added"

    if apply and action != "unchanged":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")
    return action


# Each entry: display name, the file to write to, and how to tell the tool is
# actually in use. A shim is only ever written for a tool with real evidence —
# writing config for a tool the owner doesn't use would be an unrequested
# change to their environment, not a convenience.
SHIM_TARGETS = {
    "claude": {
        "path": lambda: Path("~/.claude/CLAUDE.md").expanduser(),
        "detect": lambda: Path("~/.claude").expanduser().is_dir(),
    },
    "aider": {
        "path": lambda: Path("~/.aider.conf.yml").expanduser(),
        "detect": lambda: (
            Path("~/.aider.conf.yml").expanduser().is_file() or _command_exists("aider")
        ),
    },
}


def _command_exists(name: str) -> bool:
    return any(
        (Path(directory) / name).is_file()
        for directory in os.environ.get("PATH", "").split(os.pathsep)
        if directory
    )


def install_shims(lcp_home: Path, apply: bool = True) -> dict[str, str]:
    """Write or refresh the managed block in every detected tool's global
    config. Returns {tool: outcome}, where outcome is added, updated,
    unchanged, or not-detected."""
    results: dict[str, str] = {}
    for tool, spec in SHIM_TARGETS.items():
        if not spec["detect"]():
            results[tool] = "not-detected"
            continue
        path = spec["path"]()
        results[tool] = _upsert_managed_block(path, lcp_home, apply)
    return results
