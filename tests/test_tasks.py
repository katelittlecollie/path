"""Tests for scripts/tasks.py — the task lifecycle.

The invariants worth defending here are the ones a human or an agent would
otherwise have to remember: identifiers are never reused, a transition is legal
or refused, and `completed` is set if and only if the status is complete.
"""

import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import okf  # noqa: E402
import tasks  # noqa: E402

TODAY = date.today().isoformat()


class TaskFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".path"
        for directory in ("tasks", "requirements", "blueprints", "build-log"):
            (self.root / directory).mkdir(parents=True)
        shutil.copy(
            Path(__file__).resolve().parents[1] / "tasks" / "TASK-TEMPLATE.md",
            self.root / "tasks" / "TASK-TEMPLATE.md",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def meta(self, task_id):
        return okf.load(tasks.find_task(self.root, task_id)).path_meta


class TestFibonacci(unittest.TestCase):
    """The scale has no ceiling. A cap would compress every large task into one
    bucket and make the hardest work in a project indistinguishable from the
    merely big."""

    def test_documented_points_are_accepted(self):
        for value in (1, 2, 3, 5, 8, 13, 21):
            self.assertTrue(tasks.is_fibonacci(value), value)

    def test_the_sequence_continues_past_the_documented_table(self):
        for value in (34, 55, 89, 144, 233):
            self.assertTrue(tasks.is_fibonacci(value), value)

    def test_non_fibonacci_numbers_are_rejected(self):
        for value in (4, 6, 7, 9, 12, 14, 20, 22, 100):
            self.assertFalse(tasks.is_fibonacci(value), value)

    def test_rubbish_is_rejected(self):
        for value in (0, -5, None, "8", 8.0, True):
            self.assertFalse(tasks.is_fibonacci(value), value)


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(tasks.slugify("Wire up the Widget"), "wire-up-the-widget")

    def test_punctuation_and_runs(self):
        self.assertEqual(tasks.slugify("Fix: the  thing!! (again)"), "fix-the-thing-again")

    def test_unicode_is_dropped(self):
        self.assertEqual(tasks.slugify("Café — naïve"), "caf-na-ve")

    def test_empty_slug_raises(self):
        with self.assertRaises(tasks.TaskError):
            tasks.slugify("!!!")


class TestNewTask(TaskFixture):
    def test_creates_valid_frontmatter(self):
        path = tasks.new_task(self.root, "Wire up the widget", effort=3)
        doc = okf.load(path)
        self.assertEqual(doc.type, "Task")
        meta = doc.path_meta
        self.assertEqual(meta["id"], "T-001")
        self.assertEqual(meta["status"], "pending")
        self.assertEqual(meta["effort"], 3)
        self.assertEqual(meta["created"], TODAY)
        self.assertIsNone(meta["completed"])

    def test_project_defaults_to_parent_dir_name_for_nested_layout(self):
        """A consumer project nests its docs at `<project>/.path/`, so the
        project is the parent — see `okf.project_dir`."""
        path = tasks.new_task(self.root, "Wire up the widget")
        doc = okf.load(path)
        self.assertEqual(doc.path_meta["project"], self.root.parent.name)

    def test_project_defaults_to_root_name_for_self_hosted_layout(self):
        """Path's own repository is self-hosted with its docs at the top
        level, so the project *is* the root — a `root.parent.name` default
        would wrongly resolve to the root's parent directory instead."""
        selfhosted = self.tmp / "selfhosted-repo"
        for directory in ("tasks", "requirements", "blueprints", "build-log"):
            (selfhosted / directory).mkdir(parents=True)
        shutil.copy(
            Path(__file__).resolve().parents[1] / "tasks" / "TASK-TEMPLATE.md",
            selfhosted / "tasks" / "TASK-TEMPLATE.md",
        )

        path = tasks.new_task(selfhosted, "Wire up the widget")
        doc = okf.load(path)
        self.assertEqual(doc.path_meta["project"], "selfhosted-repo")

    def test_filename_matches_id_and_slug(self):
        path = tasks.new_task(self.root, "Wire up the widget")
        self.assertEqual(path.name, "T-001-wire-up-the-widget.md")

    def test_title_lands_in_frontmatter_and_body(self):
        path = tasks.new_task(self.root, "Wire up the widget")
        doc = okf.load(path)
        self.assertEqual(doc.meta["title"], "Wire up the widget")
        self.assertIn("# Wire up the widget", doc.body)

    def test_ids_are_sequential(self):
        tasks.new_task(self.root, "First")
        tasks.new_task(self.root, "Second")
        self.assertEqual(tasks.new_task(self.root, "Third").name.split("-")[1], "003")

    def test_id_of_a_referenced_deleted_task_is_not_reused(self):
        """A number the history refers to stays dead (F-36).

        Reusing it would leave the build log describing two different pieces of
        work under one id, and the log is the thing that has to stay
        trustworthy.
        """
        tasks.new_task(self.root, "First")
        second = tasks.new_task(self.root, "Second")
        (self.root / "build-log" / "2026-07-16-retro.md").write_text(
            "---\ntype: Build Log Entry\n---\n\nRETROSPECTIVE — T-002 went fine.\n"
        )
        second.unlink()
        self.assertEqual(tasks.next_id(self.root), "T-003")

    def test_id_referenced_only_by_agents_md_is_not_reused(self):
        tasks.new_task(self.root, "First")
        tasks.new_task(self.root, "Second").unlink()
        (self.tmp / "AGENTS.md").write_text("## Current Task\n\nT-002 (pending) — Second\n")
        self.assertEqual(tasks.next_id(self.root), "T-003")

    def test_unreferenced_deleted_id_may_be_reused(self):
        """The honest residual: if nothing ever mentioned it, there is no
        history to make ambiguous, so the number is free."""
        tasks.new_task(self.root, "First")
        tasks.new_task(self.root, "Second").unlink()
        self.assertEqual(tasks.next_id(self.root), "T-002")

    def test_effort_off_scale_is_refused(self):
        with self.assertRaises(tasks.TaskError):
            tasks.new_task(self.root, "Nope", effort=4)

    def test_large_fibonacci_effort_is_accepted(self):
        """lcm's WO-036 is a 21. Nothing about the scale stops at 13."""
        path = tasks.new_task(self.root, "Enormous", effort=21)
        self.assertEqual(okf.load(path).path_meta["effort"], 21)

    def test_effort_may_be_omitted(self):
        meta = okf.load(tasks.new_task(self.root, "No estimate")).path_meta
        self.assertIsNone(meta["effort"])

    def test_requires_must_exist(self):
        with self.assertRaises(tasks.TaskError):
            tasks.new_task(self.root, "Depends on a ghost", requires=["T-404"])

    def test_requires_existing_task_is_accepted(self):
        tasks.new_task(self.root, "First")
        path = tasks.new_task(self.root, "Second", requires=["T-001"])
        self.assertEqual(okf.load(path).path_meta["requires"], ["T-001"])

    def test_template_frontmatter_is_valid_yaml(self):
        """The template's own frontmatter has to parse, or nothing can be created.

        `title: [Short Descriptive Title]` looks like a blank to fill in and is
        actually a YAML flow sequence; a `?` inside one is a parse error.
        """
        doc = okf.load(self.root / "tasks" / "TASK-TEMPLATE.md")
        self.assertEqual(doc.type, "Task")


class TestTransitions(TaskFixture):
    def setUp(self):
        super().setUp()
        tasks.new_task(self.root, "Thing", effort=3)

    def test_start(self):
        tasks.transition(self.root, "T-001", "in-progress")
        self.assertEqual(self.meta("T-001")["status"], "in-progress")

    def test_complete_stamps_the_date(self):
        tasks.transition(self.root, "T-001", "in-progress")
        tasks.transition(self.root, "T-001", "complete")
        meta = self.meta("T-001")
        self.assertEqual(meta["status"], "complete")
        self.assertEqual(meta["completed"], TODAY)

    def test_complete_records_who(self):
        tasks.transition(self.root, "T-001", "in-progress")
        tasks.transition(self.root, "T-001", "complete", by="claude-opus-4-8")
        self.assertEqual(self.meta("T-001")["completed_by"], ["claude-opus-4-8"])

    def test_cannot_complete_without_starting(self):
        with self.assertRaises(tasks.TaskError) as ctx:
            tasks.transition(self.root, "T-001", "complete")
        self.assertIn("cannot become", str(ctx.exception))

    def test_cannot_transition_to_current_status(self):
        with self.assertRaises(tasks.TaskError):
            tasks.transition(self.root, "T-001", "pending")

    def test_reopening_clears_the_completed_date(self):
        """The iff that keeps burn-up honest, in the direction people forget."""
        tasks.transition(self.root, "T-001", "in-progress")
        tasks.transition(self.root, "T-001", "complete")
        tasks.transition(self.root, "T-001", "in-progress")
        meta = self.meta("T-001")
        self.assertEqual(meta["status"], "in-progress")
        self.assertIsNone(meta["completed"])

    def test_block_and_unblock(self):
        tasks.transition(self.root, "T-001", "blocked")
        self.assertEqual(self.meta("T-001")["status"], "blocked")
        tasks.transition(self.root, "T-001", "in-progress")
        self.assertEqual(self.meta("T-001")["status"], "in-progress")

    def test_unknown_task_raises(self):
        with self.assertRaises(tasks.TaskError):
            tasks.transition(self.root, "T-404", "in-progress")

    def test_transition_updates_the_updated_date(self):
        tasks.transition(self.root, "T-001", "in-progress")
        self.assertEqual(self.meta("T-001")["updated"], TODAY)


class TestLogging(TaskFixture):
    def setUp(self):
        super().setUp()
        tasks.new_task(self.root, "Thing", effort=3)

    def test_change_captures_status_automatically(self):
        """The volatility chart classifies impact from this; a value supplied
        after the fact would be a guess."""
        tasks.transition(self.root, "T-001", "in-progress")
        tasks.log(self.root, "change", "T-001", "Widened the scope")
        entry = self.meta("T-001")["change_log"][0]
        self.assertEqual(entry["status_at_change"], "in-progress")
        self.assertEqual(entry["date"], TODAY)
        self.assertEqual(entry["note"], "Widened the scope")

    def test_change_at_pending_is_low_impact(self):
        tasks.log(self.root, "change", "T-001", "Tweaked before starting")
        self.assertEqual(self.meta("T-001")["change_log"][0]["status_at_change"], "pending")

    def test_drift_entry(self):
        tasks.log(
            self.root, "drift", "T-001", "Approach corrected",
            drift_kind="correction", effort_to_correct=2,
        )
        entry = self.meta("T-001")["drift_log"][0]
        self.assertEqual(entry["kind"], "correction")
        self.assertEqual(entry["effort_to_correct"], 2)

    def test_drift_requires_a_known_kind(self):
        with self.assertRaises(tasks.TaskError):
            tasks.log(self.root, "drift", "T-001", "x", drift_kind="vibes", effort_to_correct=1)

    def test_drift_effort_is_bounded(self):
        with self.assertRaises(tasks.TaskError):
            tasks.log(self.root, "drift", "T-001", "x", drift_kind="retry", effort_to_correct=5)

    def test_issue_entry(self):
        tasks.log(self.root, "issue", "T-001", "Broken link", resolution="Fixed")
        entry = self.meta("T-001")["issues"][0]
        self.assertEqual(entry["note"], "Broken link")
        self.assertEqual(entry["resolution"], "Fixed")

    def test_issue_without_resolution_is_allowed(self):
        tasks.log(self.root, "issue", "T-001", "Still looking into it")
        self.assertIsNone(self.meta("T-001")["issues"][0]["resolution"])

    def test_entries_accumulate(self):
        tasks.log(self.root, "change", "T-001", "one")
        tasks.log(self.root, "change", "T-001", "two")
        self.assertEqual(len(self.meta("T-001")["change_log"]), 2)

    def test_unknown_kind_raises(self):
        with self.assertRaises(tasks.TaskError):
            tasks.log(self.root, "vibes", "T-001", "x")


if __name__ == "__main__":
    unittest.main()
