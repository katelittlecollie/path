"""Tests for scripts/graphify_check.py.

Every side-effecting call — finding the binary, running a subprocess, checking
a TTY, reading a prompt answer — is injected. Nothing here ever shells out to a
real `uv`/`pipx`/`pip`, and nothing ever touches PyPI. That is the whole point:
this module offers to install software, so its tests have to prove the offer
behaves exactly as documented without spending the side effect for real.

The test names below map directly onto the verification checklist in the
approved plan for this feature: present-and-current says nothing; absent
prompts and defaults to no; accepting runs the right command; below the
version floor triggers an upgrade offer; no TTY never blocks; declining
sticks; a failed install is reported honestly.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import graphify_check  # noqa: E402
import profile as profile_mod  # noqa: E402


def fake_run(stdout="", stderr="", returncode=0):
    def _run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)
    return _run


def which_finding(*names):
    """A `which` stand-in that only resolves the given command names."""
    def _which(name):
        return f"/fake/bin/{name}" if name in names else None
    return _which


class GraphifyFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.lcp_home = self.tmp / "lcp"
        profile_mod.ensure_scaffold(self.lcp_home)

    def tearDown(self):
        shutil.rmtree(self.tmp)


class TestVersionParsing(unittest.TestCase):
    def test_parses_from_plain_output(self):
        self.assertEqual(graphify_check.version_tuple("graphify 0.8.37"), (0, 8, 37))

    def test_tuple_comparison(self):
        self.assertLess(graphify_check.version_tuple("0.8.0"), graphify_check.version_tuple("0.8.37"))

    def test_unparseable_returns_none(self):
        self.assertIsNone(graphify_check.version_tuple("nonsense"))


class TestPickInstallMethod(unittest.TestCase):
    def test_prefers_uv(self):
        self.assertEqual(graphify_check.pick_install_method(which=which_finding("uv", "pipx")), "uv")

    def test_falls_back_to_pipx(self):
        self.assertEqual(graphify_check.pick_install_method(which=which_finding("pipx")), "pipx")

    def test_falls_back_to_pip_when_nothing_else_present(self):
        self.assertEqual(graphify_check.pick_install_method(which=which_finding()), "pip")

    def test_install_command_uses_the_two_y_package_name(self):
        """The CLI is `graphify`; the package is `graphifyy`. Get this backwards
        and the installer either fails or installs the wrong thing."""
        self.assertIn("graphifyy", graphify_check.INSTALL_METHODS["uv"])
        self.assertNotIn("graphify", [
            a for a in graphify_check.INSTALL_METHODS["uv"] if a != "graphifyy"
        ])
        self.assertEqual(
            graphify_check.INSTALL_METHODS["uv"],
            ["uv", "tool", "install", "--upgrade", "graphifyy"],
        )


class TestPresentAndCurrent(GraphifyFixture):
    def test_says_and_does_nothing(self):
        """Verification case 1: on a machine with graphify already at or above
        the floor, `path install` must say nothing and install nothing."""
        calls = []
        result = graphify_check.check_and_maybe_install(
            self.lcp_home,
            which=which_finding("graphify"),
            run=fake_run("graphify 9.9.9"),
            isatty=lambda: True,
            input_fn=lambda *_: (calls.append("prompted") or "y"),
            output=lambda *_: calls.append("printed"),
        )
        self.assertEqual(result.action, "none")
        self.assertTrue(result.found)
        self.assertTrue(result.meets_floor)
        self.assertEqual(calls, [])  # no prompt, no output — nothing happened


class TestAbsentAndInteractive(GraphifyFixture):
    def test_prompts_and_defaults_to_no(self):
        """Verification case 2: absent -> prompts; hitting enter (empty
        string) declines, per 'default is no'."""
        result = graphify_check.check_and_maybe_install(
            self.lcp_home,
            which=which_finding(),  # graphify nowhere on PATH
            run=fake_run(),
            isatty=lambda: True,
            input_fn=lambda *_: "",  # user just hits enter
            output=lambda *_: None,
        )
        self.assertEqual(result.action, "declined")

    def test_declining_leaves_path_working(self):
        """No exception, no crash — a decline is a normal, supported outcome."""
        try:
            graphify_check.check_and_maybe_install(
                self.lcp_home, which=which_finding(), run=fake_run(),
                isatty=lambda: True, input_fn=lambda *_: "n", output=lambda *_: None,
            )
        except Exception as exc:  # noqa: BLE001
            self.fail(f"declining raised: {exc}")

    def test_explicit_yes_or_variants_confirm(self):
        for answer in ("y", "Y", "yes", "YES"):
            with self.subTest(answer=answer):
                lcp = self.tmp / f"lcp-{answer}"
                profile_mod.ensure_scaffold(lcp)
                result = graphify_check.check_and_maybe_install(
                    lcp, which=which_finding(),
                    run=lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""),
                    isatty=lambda: True, input_fn=lambda *_: answer, output=lambda *_: None,
                )
                self.assertIn(result.action, ("installed", "failed"))  # confirmed, not declined


class TestAcceptingInstalls(GraphifyFixture):
    def test_runs_the_documented_uv_command(self):
        """Verification case 3: accepting must run
        `uv tool install --upgrade graphifyy`, not `graphify`."""
        recorded = []

        # which() reports graphify present only *after* install is attempted.
        state = {"installed": False}

        def which(name):
            if name == "uv":
                return "/opt/homebrew/bin/uv"
            if name == "graphify" and state["installed"]:
                return "/fake/bin/graphify"
            return None

        def run(*args, **kwargs):
            recorded.append(args[0])
            if args[0][0] == "uv":
                state["installed"] = True
            return subprocess.CompletedProcess(args[0], 0, "graphify 9.9.9", "")

        graphify_check.check_and_maybe_install(
            self.lcp_home, which=which, run=run,
            isatty=lambda: True, input_fn=lambda *_: "y", output=lambda *_: None,
        )
        self.assertIn(["uv", "tool", "install", "--upgrade", "graphifyy"], recorded)


class TestBelowVersionFloor(GraphifyFixture):
    def test_upgrade_offer_fires(self):
        """Verification case 4: present but below the configured minimum
        triggers the same offer, worded as an upgrade."""
        config = profile_mod.load_config(self.lcp_home)
        config["graphify_min_version"] = "9.0.0"
        profile_mod.save_config(self.lcp_home, config)

        prompts = []
        result = graphify_check.check_and_maybe_install(
            self.lcp_home,
            which=which_finding("graphify", "uv"),
            run=fake_run("graphify 0.8.37"),
            isatty=lambda: True,
            input_fn=lambda text: (prompts.append(text) or "n"),
            output=lambda *_: None,
        )
        self.assertEqual(result.action, "declined")
        self.assertTrue(any("upgrade" in p.lower() for p in prompts), prompts)

    def test_at_the_floor_is_current(self):
        config = profile_mod.load_config(self.lcp_home)
        config["graphify_min_version"] = "0.8.37"
        profile_mod.save_config(self.lcp_home, config)
        result = graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding("graphify"), run=fake_run("graphify 0.8.37"),
            isatty=lambda: True, input_fn=lambda *_: "n", output=lambda *_: None,
        )
        self.assertEqual(result.action, "none")


class TestNonInteractive(GraphifyFixture):
    def test_never_prompts_without_a_tty(self):
        """Verification case 5: `path .` (or anything) with no terminal
        attached must not hang. Prove it by making input_fn raise — if it's
        ever called, the test fails immediately instead of hanging."""
        def explode(*_a, **_k):
            raise AssertionError("prompted with no TTY attached")

        result = graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding(), run=fake_run(),
            isatty=lambda: False, input_fn=explode, output=lambda *_: None,
        )
        self.assertEqual(result.action, "skipped-no-tty")

    def test_prints_the_manual_command(self):
        printed = []
        graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding("uv"), run=fake_run(),
            isatty=lambda: False, input_fn=lambda *_: (_ for _ in ()).throw(AssertionError()),
            output=lambda msg: printed.append(msg),
        )
        self.assertTrue(any("uv tool install" in msg for msg in printed), printed)

    def test_does_not_write_config_on_a_no_tty_skip(self):
        """Skipping is not the same as declining — it must not be remembered,
        since the environment (not the owner) made this call."""
        graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding(), run=fake_run(),
            isatty=lambda: False, input_fn=lambda *_: "y", output=lambda *_: None,
        )
        self.assertNotEqual(profile_mod.load_config(self.lcp_home).get("graphify"), "off")


class TestDecliningSticks(GraphifyFixture):
    def test_decline_writes_config_off(self):
        graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding(), run=fake_run(),
            isatty=lambda: True, input_fn=lambda *_: "n", output=lambda *_: None,
        )
        self.assertEqual(profile_mod.load_config(self.lcp_home)["graphify"], "off")

    def test_second_call_does_not_reask(self):
        graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding(), run=fake_run(),
            isatty=lambda: True, input_fn=lambda *_: "n", output=lambda *_: None,
        )

        def explode(*_a, **_k):
            raise AssertionError("re-asked after a remembered decline")

        result = graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding(), run=fake_run(),
            isatty=lambda: True, input_fn=explode, output=lambda *_: None,
        )
        self.assertEqual(result.action, "remembered-off")

    def test_force_flag_asks_again(self):
        """`path install --graphify` re-asks even after a remembered decline."""
        graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding(), run=fake_run(),
            isatty=lambda: True, input_fn=lambda *_: "n", output=lambda *_: None,
        )
        asked = []
        graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding(), run=fake_run(),
            force=True, isatty=lambda: True,
            input_fn=lambda *_: (asked.append(True) or "n"), output=lambda *_: None,
        )
        self.assertEqual(asked, [True])

    def test_no_graphify_flag_declines_without_prompting(self):
        def explode(*_a, **_k):
            raise AssertionError("prompted despite --no-graphify")

        result = graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding(), run=fake_run(),
            decline=True, isatty=lambda: True, input_fn=explode, output=lambda *_: None,
        )
        self.assertEqual(result.action, "declined")
        self.assertEqual(profile_mod.load_config(self.lcp_home)["graphify"], "off")

    def test_yes_flag_preconfirms_without_prompting(self):
        def explode(*_a, **_k):
            raise AssertionError("prompted despite --yes")

        result = graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding("uv"),
            run=fake_run("graphify 9.9.9"),
            assume_yes=True, isatty=lambda: True, input_fn=explode, output=lambda *_: None,
        )
        self.assertNotEqual(result.action, "declined")


class TestFailedInstall(GraphifyFixture):
    def test_reported_honestly_even_with_a_zero_exit_code(self):
        """Verification case 7: whatever the installer's own exit code says,
        the truth is whether `graphify` actually resolves afterward."""
        def run(*args, **kwargs):
            # Exits 0, but the binary never actually lands on PATH — the
            # scenario a bad package index or a broken venv produces.
            return subprocess.CompletedProcess(args[0], 0, "", "")

        result = graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding("uv"), run=run,  # graphify itself never found
            isatty=lambda: True, input_fn=lambda *_: "y", output=lambda *_: None,
        )
        self.assertEqual(result.action, "failed")
        self.assertTrue(result.warnings)

    def test_failed_install_does_not_set_graphify_off(self):
        """A failed yes is not a decline — the next run should try again, not
        silently suppress itself."""
        def run(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, "", "")

        graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding("uv"), run=run,
            isatty=lambda: True, input_fn=lambda *_: "y", output=lambda *_: None,
        )
        self.assertNotEqual(profile_mod.load_config(self.lcp_home).get("graphify"), "off")

    def test_stderr_is_surfaced_in_the_warning(self):
        def run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args[0], 1, "", "ERROR: could not find a version that satisfies graphifyy"
            )

        result = graphify_check.check_and_maybe_install(
            self.lcp_home, which=which_finding("uv"), run=run,
            isatty=lambda: True, input_fn=lambda *_: "y", output=lambda *_: None,
        )
        self.assertTrue(any("graphifyy" in w for w in result.warnings), result.warnings)


class TestDetectIsReadOnly(GraphifyFixture):
    """`path doctor` calls detect() and must never be able to trigger a
    prompt or an install — a status command cannot have that as a side
    effect, even a rare one."""

    def test_detect_never_prompts(self):
        result = graphify_check.detect(
            self.lcp_home, which=which_finding(), run=fake_run()
        )
        self.assertEqual(result.found, False)

    def test_detect_has_no_input_or_output_parameters(self):
        import inspect
        params = inspect.signature(graphify_check.detect).parameters
        self.assertNotIn("input_fn", params)
        self.assertNotIn("output", params)

    def test_detect_reports_version_and_floor(self):
        result = graphify_check.detect(
            self.lcp_home, which=which_finding("graphify"), run=fake_run("graphify 0.8.37")
        )
        self.assertEqual(result.version, "0.8.37")
        self.assertTrue(result.meets_floor)  # default floor is 0.8.0


if __name__ == "__main__":
    unittest.main()
