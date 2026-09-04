"""Tests for scripts/graphify_run.py.

A real `graphify` build can call an LLM per file in some modes, so nothing
here ever runs the actual command — every subprocess call is injected, the
same discipline as test_graphify_check.py. What's being verified is the
contract: incremental vs full build is chosen correctly, and nothing that can
go wrong here is allowed to propagate as a failure (F-50).
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import graphify_run  # noqa: E402


class RunFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)


class TestGraphExists(RunFixture):
    def test_false_when_absent(self):
        self.assertFalse(graphify_run.graph_exists(self.tmp))

    def test_true_when_present(self):
        out = self.tmp / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text("{}")
        self.assertTrue(graphify_run.graph_exists(self.tmp))

    def test_false_when_directory_exists_but_no_graph_file(self):
        (self.tmp / "graphify-out").mkdir()
        self.assertFalse(graphify_run.graph_exists(self.tmp))


class TestRunChoosesIncrementalOrFull(RunFixture):
    def test_full_build_when_no_existing_graph(self):
        recorded = []

        def run(args, **kwargs):
            recorded.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")

        graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        self.assertEqual(recorded[0], ["graphify", "extract", str(self.tmp)])

    def test_incremental_when_graph_already_exists(self):
        out = self.tmp / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text("{}")

        recorded = []

        def run(args, **kwargs):
            recorded.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")

        graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        self.assertEqual(recorded[0], ["graphify", "update", str(self.tmp)])

    def test_runs_with_project_dir_as_cwd(self):
        captured = {}

        def run(args, **kwargs):
            captured["cwd"] = kwargs.get("cwd")
            return subprocess.CompletedProcess(args, 0, "", "")

        graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        self.assertEqual(captured["cwd"], str(self.tmp))


class TestNeverFatal(RunFixture):
    """F-50: nothing about the graph is allowed to fail the operation it's
    attached to. Every branch here returns cleanly instead of raising."""

    def test_binary_missing_does_not_raise(self):
        def run(args, **kwargs):
            raise FileNotFoundError("no such file: graphify")

        result = graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        self.assertFalse(result)

    def test_timeout_does_not_raise(self):
        def run(args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args, timeout=1)

        result = graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        self.assertFalse(result)

    def test_nonzero_exit_does_not_raise(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 1, "", "boom")

        result = graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        self.assertFalse(result)

    def test_os_error_does_not_raise(self):
        def run(args, **kwargs):
            raise OSError("permission denied")

        result = graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        self.assertFalse(result)

    def test_success_reports_true(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "", "")

        result = graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        self.assertTrue(result)

    def test_failure_output_mentions_the_project_did_not_stop(self):
        messages = []

        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 1, "", "some real error from graphify")

        graphify_run.run(self.tmp, run=run, output=lambda m: messages.append(m))
        self.assertTrue(any("continuing without" in m for m in messages), messages)
        self.assertTrue(any("some real error from graphify" in m for m in messages), messages)


class TestUsageBannerIsNotSuccess(RunFixture):
    """A wrong invocation does not always exit non-zero. graphify answers an
    unrecognised subcommand with its usage banner and exit 0, which is how the
    T-026 bug went unnoticed: the wrapper reported a graph it never built."""

    USAGE = "Usage: graphify <command>\n\nCommands:\n  install\n  update\n"

    def test_usage_banner_on_zero_exit_is_not_success(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, self.USAGE, "")

        result = graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        self.assertFalse(result)

    def test_usage_banner_says_why_rather_than_claiming_a_build(self):
        messages = []

        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, self.USAGE, "")

        graphify_run.run(self.tmp, run=run, output=lambda m: messages.append(m))
        self.assertTrue(any("usage" in m for m in messages), messages)
        self.assertFalse(any("built the knowledge graph" in m for m in messages), messages)

    def test_real_build_output_is_still_success(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(
                args, 0, "[graphify extract] wrote graph.json: 3 nodes, 3 edges\n", ""
            )

        self.assertTrue(graphify_run.run(self.tmp, run=run, output=lambda *_: None))

    def test_subcommand_names_a_real_graphify_command(self):
        """Guards the specific defect: neither arm may pass an option where a
        subcommand belongs."""
        recorded = []

        def run(args, **kwargs):
            recorded.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")

        graphify_run.run(self.tmp, run=run, output=lambda *_: None)
        out = self.tmp / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text("{}")
        graphify_run.run(self.tmp, run=run, output=lambda *_: None)

        for args in recorded:
            self.assertIn(args[1], {"extract", "update"}, args)
            self.assertFalse(args[1].startswith("-"), args)


class TestColdStartFallback(RunFixture):
    """`graphify extract` refuses a doc-heavy corpus when no LLM API key is
    set, and most Path projects are documentation. Path runs unattended with
    no key to offer, so rather than leaving those projects graphless it falls
    back to the AST-only path — and says that is what happened."""

    NO_KEY = "error: no LLM API key found (34 doc/paper/image file(s) need semantic extraction)."

    def _runner(self, recorded, results):
        def run(args, **kwargs):
            recorded.append(args)
            return results.pop(0)
        return run

    def test_falls_back_to_update_when_full_build_refuses(self):
        recorded = []
        results = [
            subprocess.CompletedProcess([], 1, "", self.NO_KEY),
            subprocess.CompletedProcess([], 0, "Rebuilt: 4 nodes\n", ""),
        ]
        ok = graphify_run.run(self.tmp, run=self._runner(recorded, results),
                              output=lambda *_: None)
        self.assertTrue(ok)
        self.assertEqual(recorded[0], ["graphify", "extract", str(self.tmp)])
        self.assertEqual(recorded[1], ["graphify", "update", str(self.tmp)])

    def test_fallback_says_the_graph_is_structure_only(self):
        messages = []
        results = [
            subprocess.CompletedProcess([], 1, "", self.NO_KEY),
            subprocess.CompletedProcess([], 0, "", ""),
        ]
        graphify_run.run(self.tmp, run=self._runner([], results),
                         output=lambda m: messages.append(m))
        self.assertTrue(any("structure-only" in m for m in messages), messages)

    def test_a_successful_full_build_does_not_fall_back(self):
        recorded = []
        results = [subprocess.CompletedProcess([], 0, "wrote graph.json\n", "")]
        ok = graphify_run.run(self.tmp, run=self._runner(recorded, results),
                              output=lambda *_: None)
        self.assertTrue(ok)
        self.assertEqual(len(recorded), 1)

    def test_first_attempt_failure_is_not_reported_when_the_fallback_works(self):
        """A first try that is allowed to fail is not news. Reporting it would
        make a working run look broken."""
        messages = []
        results = [
            subprocess.CompletedProcess([], 1, "", self.NO_KEY),
            subprocess.CompletedProcess([], 0, "", ""),
        ]
        graphify_run.run(self.tmp, run=self._runner([], results),
                         output=lambda m: messages.append(m))
        self.assertFalse(any("exited with an error" in m for m in messages), messages)

    def test_both_failing_is_still_not_fatal(self):
        results = [
            subprocess.CompletedProcess([], 1, "", self.NO_KEY),
            subprocess.CompletedProcess([], 1, "", "boom"),
        ]
        ok = graphify_run.run(self.tmp, run=self._runner([], results),
                              output=lambda *_: None)
        self.assertFalse(ok)

    def test_incremental_never_falls_back(self):
        """An existing graph means update is the right command; a failure
        there is a real failure, not a signal to try something else."""
        out = self.tmp / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text("{}")

        recorded = []
        results = [subprocess.CompletedProcess([], 1, "", "boom")]
        ok = graphify_run.run(self.tmp, run=self._runner(recorded, results),
                              output=lambda *_: None)
        self.assertFalse(ok)
        self.assertEqual(len(recorded), 1)


if __name__ == "__main__":
    unittest.main()
