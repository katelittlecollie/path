"""Tests for scripts/next.py — readiness, ranking, and what to start.

The defect these exist to prevent is concrete: the old queue sorted pending
tasks by identifier and never looked at `requires`, so it named tasks that
could not be started and gave the reader no way to tell which. Every test here
is built from hand-made rows, the same way the metrics tests are, so the rules
can be checked by reading them.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import next as next_mod  # noqa: E402


def row(task_id, status="pending", effort=3, requires=None, batch=None, title=None):
    return {
        "id": task_id,
        "status": status,
        "effort": effort,
        "requires": requires or [],
        "batch": batch,
        "implements": [],
        "_title": title or f"task {task_id}",
    }


def ids(entries):
    return [e["id"] for e in entries]


class TestReadiness(unittest.TestCase):
    def test_a_pending_task_with_no_prerequisites_is_ready(self):
        got = next_mod.readiness([row("T-001")])
        self.assertEqual(ids(got["ready"]), ["T-001"])

    def test_a_pending_task_with_an_incomplete_prerequisite_is_not_ready(self):
        """The defect the identifier sort had: T-001 sorts first and cannot start."""
        rows = [row("T-002", status="in-progress"), row("T-001", requires=["T-002"])]
        got = next_mod.readiness(rows)
        self.assertEqual(ids(got["ready"]), [])
        self.assertEqual(ids(got["waiting"]), ["T-001"])
        self.assertEqual(got["waiting"][0]["needs"], ["T-002"])

    def test_a_prerequisite_merely_in_progress_does_not_satisfy(self):
        rows = [row("T-001", status="in-progress"), row("T-002", requires=["T-001"])]
        self.assertEqual(ids(next_mod.readiness(rows)["ready"]), [])

    def test_a_completed_prerequisite_satisfies(self):
        rows = [row("T-001", status="complete"), row("T-002", requires=["T-001"])]
        self.assertEqual(ids(next_mod.readiness(rows)["ready"]), ["T-002"])

    def test_a_prerequisite_that_does_not_exist_does_not_satisfy(self):
        """A broken reference is a check failure; treating it as met here would
        promote the task to the top of the queue on the strength of a typo."""
        got = next_mod.readiness([row("T-001", requires=["T-404"])])
        self.assertEqual(ids(got["ready"]), [])
        self.assertEqual(got["waiting"][0]["needs"], ["T-404"])

    def test_blocked_is_reported_apart_from_waiting(self):
        """One is a fact about the graph and clears itself; the other is a
        person declaring an obstacle and does not."""
        rows = [row("T-001", status="blocked"), row("T-003", requires=["T-002"]), row("T-002")]
        got = next_mod.readiness(rows)
        self.assertEqual(ids(got["blocked"]), ["T-001"])
        self.assertEqual(ids(got["waiting"]), ["T-003"])

    def test_a_requires_cycle_is_reported_rather_than_traversed(self):
        rows = [row("T-001", requires=["T-002"]), row("T-002", requires=["T-001"])]
        got = next_mod.readiness(rows)
        self.assertEqual(ids(got["ready"]), [])
        self.assertEqual(ids(got["waiting"]), ["T-001", "T-002"])

    def test_complete_tasks_are_carried_as_entries(self):
        got = next_mod.readiness([row("T-001", status="complete", title="Done thing")])
        self.assertEqual(ids(got["complete"]), ["T-001"])
        self.assertEqual(got["complete"][0]["title"], "Done thing")

    def test_totals_account_for_every_task(self):
        rows = [row("T-001"), row("T-002", status="complete"), row("T-003", status="blocked")]
        got = next_mod.readiness(rows)
        self.assertEqual(got["total"], 3)


class TestUnblockCounts(unittest.TestCase):
    def test_counts_every_dependant(self):
        rows = [row("T-001"), row("T-002", requires=["T-001"]), row("T-003", requires=["T-001"])]
        self.assertEqual(next_mod.unblock_counts(rows)["T-001"], 2)

    def test_a_task_nothing_depends_on_has_no_count(self):
        self.assertEqual(next_mod.unblock_counts([row("T-001")]).get("T-001", 0), 0)

    def test_a_completed_dependant_still_counts(self):
        """The number is a fact about the graph, not a live queue depth."""
        rows = [row("T-001"), row("T-002", status="complete", requires=["T-001"])]
        self.assertEqual(next_mod.unblock_counts(rows)["T-001"], 1)


class TestRanking(unittest.TestCase):
    def test_the_task_unblocking_the_most_others_comes_first(self):
        rows = [
            row("T-001"),
            row("T-002"),
            row("T-003", requires=["T-002"]),
            row("T-004", requires=["T-002"]),
        ]
        self.assertEqual(ids(next_mod.readiness(rows)["ready"])[0], "T-002")

    def test_ties_break_by_identifier(self):
        rows = [row("T-002"), row("T-001")]
        self.assertEqual(ids(next_mod.readiness(rows)["ready"]), ["T-001", "T-002"])

    def test_an_in_progress_batch_outranks_the_unblock_heuristic(self):
        """A batch's sequence is an explicit human judgment about order, and an
        explicit judgment beats a computed heuristic."""
        rows = [
            row("T-001", batch="B-001"),
            row("T-002"),
            row("T-003", requires=["T-002"]),
            row("T-004", requires=["T-002"]),
        ]
        rollups = [{"id": "B-001", "status": "in-progress", "sequence": ["T-001"]}]
        self.assertEqual(ids(next_mod.readiness(rows, rollups)["ready"])[0], "T-001")

    def test_batch_members_follow_the_batch_sequence(self):
        rows = [row("T-001", batch="B-001"), row("T-002", batch="B-001")]
        rollups = [{"id": "B-001", "status": "in-progress", "sequence": ["T-002", "T-001"]}]
        self.assertEqual(ids(next_mod.readiness(rows, rollups)["ready"]), ["T-002", "T-001"])

    def test_a_pending_batch_does_not_steer_the_queue(self):
        """A pending batch is a plan, not a commitment. Letting it reorder the
        queue would make ranking depend on which batches merely exist."""
        rows = [
            row("T-001"),
            row("T-002", batch="B-001"),
            row("T-003", requires=["T-001"]),
        ]
        rollups = [{"id": "B-001", "status": "pending", "sequence": ["T-002"]}]
        self.assertEqual(ids(next_mod.readiness(rows, rollups)["ready"])[0], "T-001")


class TestNextBatch(unittest.TestCase):
    def test_the_batch_of_the_first_ready_task(self):
        rows = [row("T-001", batch="B-001")]
        rollups = [{"id": "B-001", "status": "in-progress", "sequence": ["T-001"]}]
        got = next_mod.next_batch(next_mod.readiness(rows, rollups), rollups)
        self.assertEqual(got["id"], "B-001")

    def test_falls_back_to_a_batch_already_under_way(self):
        """Nothing ready inside it is exactly when the answer is most obvious."""
        rows = [row("T-001", status="in-progress", batch="B-001")]
        rollups = [{"id": "B-001", "status": "in-progress", "sequence": ["T-001"]}]
        got = next_mod.next_batch(next_mod.readiness(rows, rollups), rollups)
        self.assertEqual(got["id"], "B-001")

    def test_a_complete_batch_is_never_returned(self):
        rows = [row("T-001", status="complete", batch="B-001")]
        rollups = [{"id": "B-001", "status": "complete", "sequence": ["T-001"]}]
        self.assertIsNone(next_mod.next_batch(next_mod.readiness(rows, rollups), rollups))

    def test_no_batches_yields_nothing(self):
        self.assertIsNone(next_mod.next_batch(next_mod.readiness([row("T-001")]), []))


class TestRendering(unittest.TestCase):
    def test_the_next_task_names_the_file_to_open(self):
        rows = [dict(row("T-001", title="Do the thing"), _path=Path("tasks/T-001-do.md"))]
        out = next_mod.render(next_mod.readiness(rows))
        self.assertIn("T-001", out)
        self.assertIn("Do the thing", out)
        self.assertIn("tasks/T-001-do.md", out)
        self.assertIn("3 pts", out)

    def test_a_task_with_no_estimate_says_so(self):
        rows = [row("T-001", effort=None)]
        self.assertIn("no estimate", next_mod.render(next_mod.readiness(rows)))

    def test_dependants_are_named_not_counted(self):
        rows = [row("T-001"), row("T-002", requires=["T-001"])]
        self.assertIn("T-002", next_mod.render(next_mod.readiness(rows)))

    def test_an_empty_queue_names_the_closest_blocker(self):
        rows = [row("T-001", status="blocked"), row("T-002", requires=["T-001"])]
        out = next_mod.render(next_mod.readiness(rows))
        self.assertIn("T-002", out)
        self.assertIn("T-001", out)

    def test_work_already_under_way_is_reported_as_such(self):
        out = next_mod.render(next_mod.readiness([row("T-001", status="in-progress")]))
        self.assertIn("in progress", out.lower())

    def test_an_all_complete_backlog_says_so(self):
        out = next_mod.render(next_mod.readiness([row("T-001", status="complete")]))
        self.assertIn("every task is complete", out)

    def test_an_empty_project_suggests_creating_a_task(self):
        self.assertIn("path new task", next_mod.render(next_mod.readiness([])))

    def test_batch_rendering_marks_each_member(self):
        rows = [
            row("T-001", status="complete", batch="B-001"),
            row("T-002", batch="B-001"),
            row("T-003", batch="B-001", requires=["T-002"]),
        ]
        rollups = [
            {
                "id": "B-001",
                "title": "First",
                "status": "in-progress",
                "sequence": ["T-001", "T-002", "T-003"],
                "tasks_done": 1,
                "tasks_total": 3,
                "points_done": 3,
                "points_total": 9,
            }
        ]
        out = next_mod.render_batch(next_mod.readiness(rows, rollups), rollups)
        self.assertIn("1. T-001", out)
        self.assertIn("done", out)
        self.assertIn("ready", out)
        self.assertIn("needs T-002", out)


class TestTaskTitle(unittest.TestCase):
    def test_the_recorded_title_wins(self):
        got = next_mod.task_title({"_title": "Real Title", "_path": Path("T-001-slugged.md")})
        self.assertEqual(got, "Real Title")

    def test_the_slug_is_the_fallback(self):
        self.assertEqual(next_mod.task_title({"_path": Path("T-001-a-slug.md")}), "a slug")

    def test_nothing_at_all_yields_empty(self):
        self.assertEqual(next_mod.task_title({}), "")


if __name__ == "__main__":
    unittest.main()
