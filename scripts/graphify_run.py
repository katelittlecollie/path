"""Build or update a project's knowledge graph. Implements F-47, F-48.

Separate from graphify_check.py on purpose: that module answers "is graphify
present and current," this one answers "given that it is, build the graph."
Neither needs the other's concerns — presence-checking has nothing to do with
subprocess timeouts, and running the graph builder has nothing to do with
PyPI package names.

Path never imports graphify as a library. It shells out to the CLI the same
way a person would from the project root, which is what keeps this module
tiny: the actual graph-building logic belongs to graphify, not to Path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

TIMEOUT_SECONDS = 900  # graphify can call an LLM per file in deep mode; give it room


def graph_exists(project_dir: Path) -> bool:
    return (project_dir / "graphify-out" / "graph.json").is_file()


def _printed_usage(proc) -> bool:
    """True if graphify answered with its usage banner instead of doing the work.

    An unrecognised subcommand is not always an error exit. graphify prints
    ``Usage: graphify <command>`` and exits 0, which a wrapper that trusts the
    return code alone will read as a successful build — and then report one.
    That is how the previous invocation bug survived: the incremental arm at
    least failed loudly, while the full-build arm claimed success and built
    nothing. Checking the output as well as the code costs one string test and
    turns a silent wrong answer into a visible one.
    """
    head = (proc.stdout or "").lstrip()[:200]
    return head.startswith("Usage: graphify")


def run(project_dir: Path, run=subprocess.run, output=print) -> bool:
    """Build the graph, or update it incrementally if one already exists.

    Returns True if the graph was built or updated, False if it was not (any
    reason at all) — which the caller must never treat as fatal. F-50 is
    unconditional: the graph is a nice-to-have, and nothing about it is
    allowed to stop `path .` from completing.
    """
    incremental = graph_exists(project_dir)

    if incremental:
        proc = _invoke(project_dir, "update", run, output)
        if proc is None:
            return False
        if not _succeeded(proc, output):
            return False
        output(f"graphify: updated the knowledge graph at {project_dir / 'graphify-out'}")
        return True

    # First run: attempt the full build, which is what F-48 asks for. It is
    # also the one that can refuse. `graphify extract` needs an LLM backend
    # for the semantic half and exits non-zero when a corpus contains docs,
    # papers, or images and no API key is set. Path shells out unattended: it
    # has no key to offer and no one to ask for one. Most Path projects are
    # documentation, so that refusal is the common case, not the edge.
    #
    # Rather than leave those projects with no graph at all, fall back to the
    # AST-only path, which needs no key and still produces graph.json. A
    # structural graph is a smaller thing than a semantic one, and saying so
    # is better than silence — the user can run graphify directly, with a key,
    # whenever they want the richer version.
    proc = _invoke(project_dir, "extract", run, output)
    if proc is None:
        return False

    if _succeeded(proc, output, quiet=True):
        output(f"graphify: built the knowledge graph at {project_dir / 'graphify-out'}")
        return True

    fallback = _invoke(project_dir, "update", run, output)
    if fallback is None:
        return False
    if not _succeeded(fallback, output):
        return False

    output(
        f"graphify: built a structure-only knowledge graph at {project_dir / 'graphify-out'} "
        "(no LLM API key, so documents were not semantically extracted)."
    )
    return True


def _invoke(project_dir: Path, subcommand: str, run, output):
    """Run one graphify subcommand. Returns None if it could not run at all.

    The three exceptions caught here are the ways the process fails to
    produce a result rather than producing a bad one, and F-50 makes all of
    them non-fatal: the graph is a nice-to-have, and nothing about it is
    allowed to stop the operation it is attached to.
    """
    args = ["graphify", subcommand, str(project_dir)]
    try:
        return run(args, cwd=str(project_dir), capture_output=True, text=True,
                   timeout=TIMEOUT_SECONDS)
    except FileNotFoundError:
        output("graphify is not on $PATH — skipping the knowledge graph.")
        return None
    except subprocess.TimeoutExpired:
        output(f"graphify did not finish within {TIMEOUT_SECONDS}s — skipping this run.")
        return None
    except OSError as exc:
        output(f"graphify failed to start ({exc}) — skipping the knowledge graph.")
        return None


def _succeeded(proc, output, quiet: bool = False) -> bool:
    """Whether a completed graphify run actually did the work.

    `quiet` suppresses the message for an attempt that has a fallback behind
    it — a first try that is allowed to fail is not news, and reporting it
    would make a working run look broken.
    """
    if proc.returncode != 0:
        if not quiet:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
            output(
                "graphify exited with an error — continuing without updating the graph."
                + ("\n  " + "\n  ".join(tail) if tail else "")
            )
        return False

    if _printed_usage(proc):
        if not quiet:
            output(
                "graphify did not recognise the command Path used and printed its usage "
                "instead — continuing without updating the graph. Path may be calling a "
                "CLI newer or older than it expects."
            )
        return False

    return True
