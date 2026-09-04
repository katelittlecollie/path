"""Check for graphify, and offer to install it. Implements F-49, F-50.

Path calls graphify as a CLI, not a library — it never imports the `graphify`
package, only shells out to the `graphify` command. So the only thing this
module needs is the binary on `$PATH` at a recent enough version; none of the
Python-interpreter detection in ~/.claude/skills/graphify/SKILL.md is relevant
here, because that exists for a caller that imports the package, and this one
does not.

Two facts drive the install logic, both easy to get backwards:

    The CLI is `graphify`. The PyPI package is `graphifyy` — two y's. Detect
    with the first name, install with the second.

Installing software is a side effect, so every path through this module that
could install something is opt-in and reversible:

    - Default answer to the prompt is no.
    - Never prompted at all without a TTY attached — an agent shelling out
      must never hang waiting on stdin that will never arrive.
    - A decline is written to config so Path stops asking, and only an
      explicit --graphify flag asks again.
    - Whatever the installer's own exit code says, the real check is whether
      `graphify` resolves and reports a version afterward.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import profile as profile_mod

PACKAGE_NAME = "graphifyy"  # not a typo — see the module docstring
CLI_NAME = "graphify"

VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

INSTALL_METHODS: dict[str, list[str]] = {
    "uv": ["uv", "tool", "install", "--upgrade", PACKAGE_NAME],
    "pipx": ["pipx", "install", PACKAGE_NAME],
    "pip": [sys.executable, "-m", "pip", "install", "--user", PACKAGE_NAME],
}


@dataclass
class CheckResult:
    """What the check found, and what — if anything — it did about it."""

    found: bool
    version: str | None = None
    meets_floor: bool = False
    action: str = "none"  # none | installed | declined | skipped-no-tty | failed | remembered-off
    detail: str = ""
    warnings: list[str] = field(default_factory=list)


def version_tuple(text: str) -> tuple[int, int, int] | None:
    match = VERSION_RE.search(text)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def find_graphify(which=shutil.which) -> str | None:
    return which(CLI_NAME)


def get_version(binary: str, run=subprocess.run) -> str | None:
    try:
        result = run([binary, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (result.stdout or "") + (result.stderr or "")
    match = VERSION_RE.search(text)
    return ".".join(match.groups()) if match else None


def detect(lcp_home: Path, which=shutil.which, run=subprocess.run) -> CheckResult:
    """Read-only: is graphify present, and does it meet the configured floor.

    Never prompts, never installs, never writes config. This is what `path
    doctor` calls — a status command must not have a side effect as a
    possibility, even a rare one.
    """
    config = profile_mod.load_config(lcp_home)
    binary = find_graphify(which=which)
    version = get_version(binary, run=run) if binary else None
    floor = str(config.get("graphify_min_version") or "0.0.0")
    meets = bool(version and version_tuple(version) and
                 version_tuple(version) >= version_tuple(floor))
    return CheckResult(found=bool(binary), version=version, meets_floor=meets)


def pick_install_method(which=shutil.which) -> str | None:
    for method in ("uv", "pipx", "pip"):
        if method == "pip" or which(method):
            return method
    return None  # pragma: no cover — pip is always available with this interpreter


def run_install(method: str, run=subprocess.run) -> subprocess.CompletedProcess:
    return run(INSTALL_METHODS[method], capture_output=True, text=True, timeout=300)


def _should_prompt(assume_yes: bool, decline: bool, isatty) -> tuple[bool, bool | None]:
    """Returns (should_ask, forced_answer). forced_answer is set when the
    caller already decided and no prompt is needed."""
    if decline:
        return False, False
    if assume_yes:
        return False, True
    if not isatty():
        return False, None  # cannot ask; caller treats this as skip-not-decline
    return True, None


def _ask(prompt_text: str, input_fn=input) -> bool:
    try:
        answer = input_fn(f"{prompt_text} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def check_and_maybe_install(
    lcp_home: Path,
    *,
    force: bool = False,
    assume_yes: bool = False,
    decline: bool = False,
    which=shutil.which,
    run=subprocess.run,
    isatty=lambda: sys.stdin.isatty(),
    input_fn=input,
    output=print,
) -> CheckResult:
    """Detect graphify, and — subject to every rule in the module docstring —
    offer to install or upgrade it.

    `force=True` is `path install --graphify`: re-ask even if a previous
    decline set `graphify: off` in config. Without it, a remembered decline is
    honoured silently.
    """
    config = profile_mod.load_config(lcp_home)
    remembered_off = config.get("graphify") == "off" and not force
    floor = str(config.get("graphify_min_version") or "0.0.0")

    result = detect(lcp_home, which=which, run=run)

    if result.found and result.meets_floor:
        return result  # present and current: say nothing, per the plan

    if remembered_off:
        result.action = "remembered-off"
        return result

    verb = "install" if not result.found else "upgrade"
    reason = (
        f"{CLI_NAME} is not installed" if not result.found
        else f"{CLI_NAME} {result.version} is older than the configured minimum {floor}"
    )

    method = pick_install_method(which=which)
    command = INSTALL_METHODS[method]

    should_ask, forced = _should_prompt(assume_yes, decline, isatty)

    if not should_ask and forced is None and not decline:
        # No TTY, and nothing pre-decided: never block waiting on input that
        # cannot arrive. Skip and say exactly what to run by hand.
        result.action = "skipped-no-tty"
        result.detail = " ".join(command)
        output(
            f"{reason}. Not prompting (no terminal attached).\n"
            f"To {verb} it yourself: {' '.join(command)}"
        )
        return result

    if decline:
        result.action = "declined"
    else:
        confirmed = forced if forced is not None else _ask(
            f"{reason}. {verb.capitalize()} {PACKAGE_NAME} via {method} ({' '.join(command)})?",
            input_fn=input_fn,
        )
        result.action = "installed" if confirmed else "declined"

        if confirmed:
            proc = run_install(method, run=run)
            new_binary = find_graphify(which=which)
            new_version = get_version(new_binary, run=run) if new_binary else None
            if new_binary and new_version:
                result.found, result.version = True, new_version
                result.meets_floor = bool(
                    version_tuple(new_version) and version_tuple(new_version) >= version_tuple(floor)
                )
                output(f"{CLI_NAME} {new_version} installed.")
            else:
                # The installer's exit code is not the truth here — whether
                # the binary actually resolves afterward is.
                result.action = "failed"
                stderr_tail = (proc.stderr or "").strip().splitlines()[-3:]
                result.warnings.append(
                    "install did not leave a working `graphify` on $PATH"
                    + (f": {' / '.join(stderr_tail)}" if stderr_tail else "")
                )
                output(
                    f"Install did not succeed — `{CLI_NAME}` still does not resolve.\n"
                    f"Try by hand: {' '.join(command)}"
                )

    if result.action == "declined":
        config["graphify"] = "off"
        profile_mod.save_config(lcp_home, config)
        output(f"Declined. Remembered — Path will not ask again ({lcp_home / 'config.yml'}).")

    return result
