"""Tests for scripts/status.py.

The queue logic — which tasks show, in what order, grouped by which status — is
exercised with hand-built frontmatter rows, the same discipline as
test_metrics.py: arithmetic and ordering a reader can check by hand. Two on-disk
tests cover the parts that need a real project: the single-project render and the
portfolio roll-up.
"""

import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import init as init_mod  # noqa: E402
import next as next_mod  # noqa: E402
import status as status_mod  # noqa: E402
import tasks as tasks_mod  # noqa: E402


def row(**overrides):
    r = {"id": "T-001", "status": "pending", "effort": 3}
    r.update(overrides)
    return r


class TestQueueLines(unittest.TestCase):
    def test_no_tasks(self):
        self.assertEqual(status_mod.queue_lines([]), ["  no tasks yet"])

    def test_counts_line_follows_status_order(self):
        rows = [
            row(id="T-001", status="complete"),
            row(id="T-002", status="pending"),
            row(id="T-003", status="in-progress"),
            row(id="T-004", status="blocked"),
        ]
        # in-progress, blocked, pending, complete — not alphabetical, not input order.
        self.assertIn("4 tasks — 1 in-progress, 1 blocked, 1 pending, 1 complete", status_mod.queue_lines(rows)[0])

    def test_unknown_status_is_shown_not_dropped(self):
        rows = [row(id="T-001", status="pending"), row(id="T-002", status="archived")]
        self.assertIn("1 archived", status_mod.queue_lines(rows)[0])

    def test_actionable_groups_present_and_ordered(self):
        rows = [
            row(id="T-005", status="in-progress"),
            row(id="T-002", status="in-progress"),
            row(id="T-003", status="blocked"),
        ]
        text = "\n".join(status_mod.queue_lines(rows))
        self.assertIn("In progress:", text)
        self.assertIn("Blocked:", text)
        # id-sorted within the in-progress group
        self.assertLess(text.index("T-002"), text.index("T-005"))

    def test_ready_collapses_past_the_cap(self):
        rows = [row(id=f"T-0{n:02d}", status="pending") for n in range(1, 9)]  # 8 ready
        text = "\n".join(status_mod.queue_lines(rows))
        self.assertIn("Ready now:", text)
        self.assertIn("and 3 more ready", text)  # 8 - SHOWN(5)
        self.assertNotIn("T-007", text)  # beyond the cap

    def test_complete_tasks_are_not_listed_as_a_queue(self):
        rows = [row(id="T-001", status="complete")]
        text = "\n".join(status_mod.queue_lines(rows))
        self.assertNotIn("T-001", text)  # counted, but not named in a queue group


class TestTaskTitle(unittest.TestCase):
    def test_the_recorded_title_wins(self):
        """`title` is ordinary OKF frontmatter, so it is the real answer.

        The slug was only ever used because `summary` returned `path_meta`
        alone; now that it carries the title too, deriving one from a filename
        is the fallback rather than the rule.
        """
        row = {
            "id": "T-040",
            "_title": "Feature: reading pane",
            "_path": Path("T-040-feature-reading-pane.md"),
        }
        self.assertEqual(status_mod.task_title(row), "Feature: reading pane")

    def test_title_from_slug_when_none_is_recorded(self):
        self.assertEqual(
            status_mod.task_title({"id": "T-040", "_path": Path("T-040-feature-reading-pane.md")}),
            "feature reading pane",
        )

    def test_no_path_yields_empty(self):
        self.assertEqual(status_mod.task_title({"id": "T-040"}), "")


class StatusOnDisk(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _project(self, name: str) -> Path:
        project = self.tmp / name
        project.mkdir()
        root, _ = init_mod.init_project(project)
        return root

    def test_render_shows_counts_and_the_in_progress_queue(self):
        root = self._project("proj")
        tasks_mod.new_task(root, title="First thing", effort=3)
        tasks_mod.new_task(root, title="Second thing", effort=5)
        tasks_mod.transition(root, "T-001", "in-progress")

        out = status_mod.render(root)
        self.assertIn("proj", out)
        self.assertIn("2 tasks", out)
        self.assertIn("1 in-progress, 1 pending", out)
        self.assertIn("In progress:", out)
        self.assertIn("T-001", out)
        self.assertIn("First thing", out)  # the recorded title, not the slug
        self.assertIn("backlog", out)
        self.assertIn("rate", out)

    def test_portfolio_one_line_per_project(self):
        a = self._project("alpha")
        b = self._project("beta")
        tasks_mod.new_task(a, title="A task", effort=8)

        out = status_mod.render_portfolio([a, b])
        self.assertIn("Portfolio — 2 projects", out)
        self.assertIn("alpha", out)
        self.assertIn("beta", out)
        self.assertIn("0/8 pts", out)  # alpha: one 8-pt pending task, none done
        # A project with nothing finished lately says so rather than showing 0.
        self.assertEqual(out.count("no recent rate"), 2)
        self.assertEqual(len(out.splitlines()), 3)  # header plus one line each


class TestReadinessInTheQueue(unittest.TestCase):
    def test_a_task_that_cannot_be_started_is_not_under_ready_now(self):
        """The defect the identifier sort had: T-001 sorts first and is unstartable."""
        rows = [
            row(id="T-001", status="pending", requires=["T-002"]),
            row(id="T-002", status="in-progress"),
        ]
        text = "\n".join(status_mod.queue_lines(rows))
        self.assertNotIn("Ready now:", text)
        self.assertIn("Waiting on prerequisites:", text)
        self.assertIn("T-001 (needs T-002)", text)

    def test_waiting_is_reported_apart_from_blocked(self):
        rows = [
            row(id="T-001", status="blocked"),
            row(id="T-002", status="pending", requires=["T-003"]),
            row(id="T-003", status="pending"),
        ]
        text = "\n".join(status_mod.queue_lines(rows))
        self.assertIn("Blocked:", text)
        self.assertIn("Waiting on prerequisites:", text)
        self.assertLess(text.index("Blocked:"), text.index("Waiting on prerequisites:"))

    def test_a_ready_line_carries_effort_batch_and_unblock_count(self):
        rows = [
            row(id="T-001", status="pending", effort=5, batch="B-001"),
            row(id="T-002", status="pending", requires=["T-001"]),
        ]
        text = "\n".join(status_mod.queue_lines(rows))
        self.assertIn("5 pts", text)
        self.assertIn("B-001", text)
        self.assertIn("unblocks 1", text)

    def test_a_task_with_no_estimate_says_so_rather_than_showing_zero(self):
        rows = [row(id="T-001", status="pending", effort=None)]
        self.assertIn("no estimate", "\n".join(status_mod.queue_lines(rows)))

    def test_batches_are_listed_with_their_progress(self):
        rows = [row(id="T-001", status="pending", batch="B-001")]
        rollups = [
            {
                "id": "B-001",
                "title": "First",
                "status": "in-progress",
                "sequence": ["T-001"],
                "tasks_done": 0,
                "tasks_total": 1,
                "points_done": 0,
                "points_total": 3,
            }
        ]
        text = "\n".join(status_mod.queue_lines(rows, rollups))
        self.assertIn("Batches:", text)
        self.assertIn("B-001  First   in-progress   0/1 tasks, 0/3 pts", text)

    def test_a_complete_batch_is_not_listed(self):
        rows = [row(id="T-001", status="complete", batch="B-001")]
        rollups = [
            {
                "id": "B-001", "title": "First", "status": "complete", "sequence": ["T-001"],
                "tasks_done": 1, "tasks_total": 1, "points_done": 3, "points_total": 3,
            }
        ]
        self.assertNotIn("Batches:", "\n".join(status_mod.queue_lines(rows, rollups)))

    def test_empty_sections_are_omitted_rather_than_left_as_headings(self):
        """An empty heading asks the reader to notice that nothing is under it."""
        text = "\n".join(status_mod.queue_lines([row(id="T-001", status="pending")]))
        for absent in ("In progress:", "Blocked:", "Batches:", "Waiting on prerequisites:"):
            self.assertNotIn(absent, text)


class TestRateLines(unittest.TestCase):
    def done(self, task_id, effort, days_ago, **extra):
        return row(
            id=task_id,
            status="complete",
            effort=effort,
            completed=(date.today() - timedelta(days=days_ago)).isoformat(),
            **extra,
        )

    def test_too_few_completions_states_the_refusal_and_prints_no_number(self):
        text = "\n".join(status_mod.rate_lines([self.done("T-001", 5, 2), row(id="T-002")]))
        self.assertIn("not enough completions in the last 14 days", text)
        self.assertNotIn("pts/week", text)
        self.assertNotIn("forecast", text)

    def test_a_measurable_rate_names_its_window(self):
        rows = [self.done("T-001", 5, 2), self.done("T-002", 9, 3), row(id="T-003", effort=14)]
        text = "\n".join(status_mod.rate_lines(rows))
        self.assertIn("pts/week over the last 14 days", text)
        self.assertIn("forecast", text)
        self.assertIn("weeks remaining", text)

    def test_unestimated_remaining_work_is_declared_as_an_under_count(self):
        rows = [
            self.done("T-001", 5, 2),
            self.done("T-002", 9, 3),
            row(id="T-003", effort=None),
        ]
        self.assertIn("carry no estimate", "\n".join(status_mod.rate_lines(rows)))


class TestOneAnswerNotTwo(unittest.TestCase):
    def test_the_first_ready_entry_matches_what_next_would_name(self):
        """Two surfaces answering one question will drift the moment either
        grows its own sorting. This is the pin that stops them."""
        rows = [
            row(id="T-001", status="pending"),
            row(id="T-002", status="pending"),
            row(id="T-003", status="pending", requires=["T-002"]),
        ]
        ready = next_mod.readiness(rows)
        first_from_next = next_mod.render(ready).splitlines()[0]
        queue = "\n".join(status_mod.queue_lines(rows))
        first_ready_line = queue.split("Ready now:")[1].strip().splitlines()[0]

        self.assertIn(ready["ready"][0]["id"], first_from_next)
        self.assertIn(ready["ready"][0]["id"], first_ready_line)


if __name__ == "__main__":
    unittest.main()
