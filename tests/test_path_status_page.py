"""Tests for scripts/path_status_page.py — the forecast banner and backlog board.

The page reads the metrics document and nothing else (F-34), so every test here
hands it a document built by hand. That is also the property most worth
defending: three surfaces now answer "what is next", and they only stay
consistent because none of them sorts or filters on its own.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import path_status_page as page  # noqa: E402


def entry(task_id, title="A task", effort=3, batch=None, needs=None):
    e = {"id": task_id, "title": title, "effort": effort, "batch": batch, "unblocks": 0}
    if needs is not None:
        e["needs"] = needs
    return e


def document(**overrides):
    data = {
        "project": "proj",
        "generated": "2026-09-04T10:00:00",
        "provenance": {"any_derived": False},
        "velocity": {
            "window_days": 14,
            "tasks": 2,
            "points": 14,
            "points_per_week": 7.0,
            "sufficient": True,
            "derived": False,
        },
        "forecast": {
            "window_days": 14,
            "points_per_week": 7.0,
            "remaining_tasks": 2,
            "remaining_points": 14,
            "unestimated": [],
            "weeks_remaining": 2.0,
            "projected_date": "2026-09-18",
            "sufficient": True,
            "derived": False,
        },
        "batches": [],
        "readiness": {
            "ready": [entry("T-001")],
            "waiting": [],
            "blocked": [],
            "in_progress": [],
            "complete": [],
            "total": 1,
        },
        "burnup": {"backlog_total": 0, "points": []},
        "volatility": [],
        "decisions": [],
        "drift": [],
        "tasks": {"total": 1, "by_status": {}, "without_effort": []},
    }
    data.update(overrides)
    return data


class TestForecastBanner(unittest.TestCase):
    def test_a_measurable_rate_shows_the_window_and_the_date(self):
        html = page.forecast_banner(document())
        self.assertIn("7.0 pts/wk", html)
        self.assertIn("last 14 days", html)
        self.assertIn("2026-09-18", html)
        self.assertIn("14 pts", html)

    def test_too_few_completions_states_it_rather_than_showing_a_zero(self):
        """A zero reads as "no progress", which is a different claim from
        "not enough completions to measure a rate"."""
        data = document()
        data["velocity"] = dict(data["velocity"], sufficient=False, points_per_week=None, tasks=1)
        data["forecast"] = dict(
            data["forecast"], sufficient=False, points_per_week=None,
            projected_date=None, weeks_remaining=None,
        )
        html = page.forecast_banner(data)
        self.assertIn("not enough to measure a rate", html)
        self.assertIn("not widened", html)
        self.assertNotIn("pts/wk", html)
        self.assertNotIn("2026-09-18", html)

    def test_a_derived_forecast_carries_the_caveat(self):
        data = document()
        data["forecast"] = dict(data["forecast"], derived=True)
        self.assertIn("model-assigned effort", page.forecast_banner(data))

    def test_unestimated_remaining_work_is_declared_an_under_count(self):
        data = document()
        data["forecast"] = dict(data["forecast"], unestimated=["T-009"])
        self.assertIn("under-count", page.forecast_banner(data))

    def test_a_document_with_no_rate_at_all_renders_nothing(self):
        self.assertEqual(page.forecast_banner({"velocity": {}, "forecast": {}}), "")


class TestBacklogBoard(unittest.TestCase):
    def test_an_empty_project_says_so(self):
        data = document()
        data["readiness"] = dict(data["readiness"], ready=[], total=0)
        self.assertIn("No tasks yet", page.backlog_board(data))

    def test_a_batch_becomes_a_group_with_its_progress(self):
        data = document()
        data["batches"] = [
            {
                "id": "B-001", "title": "First", "status": "in-progress",
                "sequence": ["T-001"], "tasks_done": 0, "tasks_total": 1,
                "points_done": 0, "points_total": 3,
            }
        ]
        data["readiness"] = dict(data["readiness"], ready=[entry("T-001", batch="B-001")])
        html = page.backlog_board(data)
        self.assertIn("B-001 First", html)
        self.assertIn("0/1 tasks, 0/3 pts", html)

    def test_a_complete_batch_is_not_rendered_as_a_group(self):
        data = document()
        data["batches"] = [
            {
                "id": "B-001", "title": "First", "status": "complete",
                "sequence": ["T-002"], "tasks_done": 1, "tasks_total": 1,
                "points_done": 3, "points_total": 3,
            }
        ]
        self.assertNotIn("B-001 First", page.backlog_board(data))

    def test_unbatched_work_gets_its_own_group(self):
        self.assertIn("Not in a batch", page.backlog_board(document()))

    def test_ready_rows_are_primary_and_waiting_rows_are_not(self):
        data = document()
        data["readiness"] = dict(
            data["readiness"],
            ready=[entry("T-001")],
            waiting=[entry("T-002", needs=["T-001"])],
            total=2,
        )
        html = page.backlog_board(data)
        ready_row = [ln for ln in html.splitlines() if "T-001" in ln][0]
        waiting_row = [ln for ln in html.splitlines() if "T-002" in ln][0]
        self.assertIn('class="row"', ready_row)
        self.assertIn('class="row secondary"', waiting_row)
        self.assertIn("needs T-001", waiting_row)

    def test_complete_work_is_collapsed_to_a_count(self):
        data = document()
        data["readiness"] = dict(
            data["readiness"], complete=[entry("T-009"), entry("T-010")], total=3
        )
        html = page.backlog_board(data)
        self.assertIn("2 task(s) complete", html)
        self.assertNotIn("T-009", html)

    def test_a_task_with_no_estimate_says_so(self):
        data = document()
        data["readiness"] = dict(data["readiness"], ready=[entry("T-001", effort=None)])
        self.assertIn("no estimate", page.backlog_board(data))

    def test_a_title_containing_markup_is_escaped(self):
        data = document()
        data["readiness"] = dict(data["readiness"], ready=[entry("T-001", title="<b>bold</b>")])
        html = page.backlog_board(data)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", html)
        self.assertNotIn("<b>bold</b>", html)


class TestWholePage(unittest.TestCase):
    def test_every_placeholder_is_filled(self):
        html = page.render_html(document())
        for placeholder in ("__PROJECT__", "__GENERATED__", "__PROVENANCE__", "__FORECAST__",
                            "__BOARD__", "__DATA__"):
            self.assertNotIn(placeholder, html)

    def test_the_board_comes_before_the_charts(self):
        """What to do next should not be below the fold behind four charts."""
        html = page.render_html(document())
        self.assertLess(html.index('id="board-section"'), html.index('id="burnup-section"'))


if __name__ == "__main__":
    unittest.main()
