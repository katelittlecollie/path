"""Tests for scripts/metrics.py.

The figures these produce are the ones people make decisions on, so the tests
lean on arithmetic that can be checked by hand rather than on golden files.

The provenance tests matter as much as the arithmetic. Some of this project's
history carries effort estimates a model assigned retrospectively and completion
dates inferred from git, and a chart that cannot distinguish those from recorded
facts is worse than no chart.
"""

import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import decisions as decisions_mod  # noqa: E402
import metrics  # noqa: E402
import okf  # noqa: E402
import tasks as tasks_mod  # noqa: E402


def task_row(**overrides):
    row = {
        "id": "T-001",
        "status": "pending",
        "effort": 3,
        "created": "2026-07-01",
        "completed": None,
        "change_log": [],
        "drift_log": [],
        "issues": [],
    }
    row.update(overrides)
    return row


class TestBurnup(unittest.TestCase):
    def test_backlog_totals_every_estimate(self):
        rows = [task_row(id="T-001", effort=3), task_row(id="T-002", effort=5)]
        self.assertEqual(metrics.burnup(rows)["backlog_total"], 8)

    def test_tasks_without_effort_do_not_count(self):
        rows = [task_row(effort=3), task_row(id="T-002", effort=None)]
        self.assertEqual(metrics.burnup(rows)["backlog_total"], 3)

    def test_completed_points_accumulate_in_date_order(self):
        rows = [
            task_row(id="T-001", effort=3, status="complete", completed="2026-07-10"),
            task_row(id="T-002", effort=5, status="complete", completed="2026-07-05"),
            task_row(id="T-003", effort=8, status="in-progress"),
        ]
        points = metrics.burnup(rows)["points"]
        self.assertEqual([(p["date"], p["completed"], p["remaining"]) for p in points],
                         [("2026-07-05", 5, 11), ("2026-07-10", 8, 8)])

    def test_complete_without_a_date_is_not_plotted(self):
        """It cannot be: there is nowhere on the x-axis to put it."""
        rows = [task_row(effort=3, status="complete", completed=None)]
        points = metrics.burnup(rows)["points"]
        self.assertEqual(points[0]["completed"], 0)

    def test_empty_project_gets_a_zero_point(self):
        points = metrics.burnup([])["points"]
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["completed"], 0)

    def test_derived_points_are_flagged(self):
        rows = [
            task_row(effort=3, status="complete", completed="2026-07-05",
                     effort_source="estimated"),
        ]
        self.assertTrue(metrics.burnup(rows)["points"][0]["derived"])

    def test_recorded_points_are_not_flagged(self):
        rows = [task_row(effort=3, status="complete", completed="2026-07-05")]
        self.assertFalse(metrics.burnup(rows)["points"][0]["derived"])


class TestVolatility(unittest.TestCase):
    def test_impact_comes_from_status_at_change(self):
        rows = [task_row(change_log=[
            {"date": "2026-07-15", "status_at_change": "pending", "note": "a"},
            {"date": "2026-07-15", "status_at_change": "in-progress", "note": "b"},
            {"date": "2026-07-15", "status_at_change": "complete", "note": "c"},
        ])]
        bucket = metrics.volatility(rows)[0]
        self.assertEqual((bucket["low"], bucket["medium"], bucket["high"]), (1, 1, 1))

    def test_entries_bucket_to_the_monday(self):
        rows = [task_row(change_log=[{"date": "2026-07-16", "status_at_change": "pending"}])]
        self.assertEqual(metrics.volatility(rows)[0]["period"], "2026-07-13")

    def test_same_week_entries_share_a_bucket(self):
        rows = [task_row(change_log=[
            {"date": "2026-07-13", "status_at_change": "pending"},
            {"date": "2026-07-17", "status_at_change": "pending"},
        ])]
        buckets = metrics.volatility(rows)
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0]["low"], 2)

    def test_unparseable_date_is_skipped_not_fatal(self):
        rows = [task_row(change_log=[{"date": "whenever", "status_at_change": "pending"}])]
        self.assertEqual(metrics.volatility(rows), [])

    def test_unknown_status_defaults_to_medium(self):
        rows = [task_row(change_log=[{"date": "2026-07-15", "status_at_change": None}])]
        self.assertEqual(metrics.volatility(rows)[0]["medium"], 1)


class TestDrift(unittest.TestCase):
    def test_drift_entries_become_events(self):
        rows = [task_row(drift_log=[
            {"date": "2026-07-15", "kind": "correction", "effort_to_correct": 2, "note": "n"}
        ])]
        event = metrics.drift(rows)[0]
        self.assertEqual((event["type"], event["effort"], event["task"]), ("correction", 2, "T-001"))

    def test_issue_after_completion_counts_as_drift(self):
        """The boundary moved after the work was declared finished, whether or
        not anyone remembered to file it as drift."""
        rows = [task_row(
            status="complete", completed="2026-07-10",
            issues=[{"date": "2026-07-14", "note": "regression"}],
        )]
        events = metrics.drift(rows)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "post-completion-bug")

    def test_issue_before_completion_is_not_drift(self):
        rows = [task_row(
            status="complete", completed="2026-07-10",
            issues=[{"date": "2026-07-08", "note": "found while working"}],
        )]
        self.assertEqual(metrics.drift(rows), [])

    def test_issue_on_an_incomplete_task_is_not_drift(self):
        rows = [task_row(status="in-progress", issues=[{"date": "2026-07-08", "note": "x"}])]
        self.assertEqual(metrics.drift(rows), [])

    def test_events_are_date_ordered(self):
        rows = [task_row(drift_log=[
            {"date": "2026-07-15", "kind": "retry", "effort_to_correct": 1},
            {"date": "2026-07-02", "kind": "correction", "effort_to_correct": 2},
        ])]
        self.assertEqual([e["date"] for e in metrics.drift(rows)], ["2026-07-02", "2026-07-15"])


class TestProvenance(unittest.TestCase):
    def test_nothing_derived(self):
        prov = metrics.provenance([task_row()])
        self.assertFalse(prov["any_derived"])
        self.assertEqual(prov["effort_estimated"], [])

    def test_estimated_effort_is_counted(self):
        prov = metrics.provenance([task_row(effort_source="estimated")])
        self.assertTrue(prov["any_derived"])
        self.assertEqual(prov["effort_estimated"], ["T-001"])

    def test_inferred_completion_is_counted(self):
        prov = metrics.provenance([task_row(completed_source="inferred-git")])
        self.assertEqual(prov["completed_inferred"], ["T-001"])

    def test_recorded_source_is_not_derived(self):
        """Only the named derivations count; an explicit 'recorded' is a fact."""
        prov = metrics.provenance([task_row(effort_source="recorded")])
        self.assertFalse(prov["any_derived"])


class TestBuild(unittest.TestCase):
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

    def test_end_to_end_from_real_files(self):
        tasks_mod.new_task(self.root, "First", effort=3)
        tasks_mod.new_task(self.root, "Second", effort=5)
        tasks_mod.transition(self.root, "T-001", "in-progress")
        tasks_mod.log(self.root, "change", "T-001", "widened")
        tasks_mod.transition(self.root, "T-001", "complete")
        decisions_mod.raise_decision(self.root, "Open question?")

        data = metrics.build(self.root)
        self.assertEqual(data["tasks"]["total"], 2)
        self.assertEqual(data["burnup"]["backlog_total"], 8)
        self.assertEqual(data["burnup"]["points"][-1]["completed"], 3)
        self.assertEqual(data["volatility"][0]["medium"], 1)
        self.assertEqual(len(data["decisions"]), 1)
        self.assertTrue(data["decisions"][0]["open"])
        self.assertFalse(data["provenance"]["any_derived"])

    def test_tasks_without_effort_are_named(self):
        tasks_mod.new_task(self.root, "No estimate")
        self.assertEqual(metrics.build(self.root)["tasks"]["without_effort"], ["T-001"])

    def test_template_is_not_counted_as_a_task(self):
        tasks_mod.new_task(self.root, "Only one")
        self.assertEqual(metrics.build(self.root)["tasks"]["total"], 1)

    def test_open_decisions_sort_first_then_oldest(self):
        decisions_mod.raise_decision(self.root, "Resolved one")
        decisions_mod.resolve_decision(self.root, 1, "answered")
        decisions_mod.raise_decision(self.root, "Open one")
        rows = metrics.decision_rows(self.root)
        self.assertTrue(rows[0]["open"])
        self.assertEqual(rows[0]["question"], "Open one")

    def test_decision_age_is_computed_not_stored(self):
        doc = decisions_mod.load(self.root)
        doc.path_meta["decisions"] = [{
            "question": "Old one", "related_task": None,
            "raised": (date.today() - timedelta(days=30)).isoformat(),
            "resolved": None, "answer": None,
        }]
        okf.save(doc)
        self.assertEqual(metrics.decision_rows(self.root)[0]["age_days"], 30)


class RateFixture(unittest.TestCase):
    """A fixed 'today' so the window boundaries can be checked by hand."""

    TODAY = date(2026, 9, 4)

    def done(self, task_id, effort, days_ago, **extra):
        return task_row(
            id=task_id,
            effort=effort,
            status="complete",
            completed=(self.TODAY - timedelta(days=days_ago)).isoformat(),
            **extra,
        )


class TestVelocity(RateFixture):
    def test_no_completions_in_the_window_is_insufficient(self):
        """Zero must produce a refusal, not a division by zero."""
        rate = metrics.velocity([task_row()], today=self.TODAY)
        self.assertFalse(rate["sufficient"])
        self.assertIsNone(rate["points_per_week"])

    def test_one_completion_is_still_insufficient(self):
        """One point establishes a position, not a slope."""
        rate = metrics.velocity([self.done("T-001", 5, 3)], today=self.TODAY)
        self.assertEqual(rate["tasks"], 1)
        self.assertFalse(rate["sufficient"])
        self.assertIsNone(rate["points_per_week"])

    def test_two_completions_give_a_weekly_rate(self):
        rows = [self.done("T-001", 5, 3), self.done("T-002", 9, 5)]
        rate = metrics.velocity(rows, today=self.TODAY)
        self.assertTrue(rate["sufficient"])
        self.assertEqual(rate["points"], 14)
        self.assertEqual(rate["points_per_week"], 7.0)  # 14 points over 14 days

    def test_a_completion_inside_the_window_edge_counts(self):
        rows = [self.done("T-001", 3, 13), self.done("T-002", 3, 1)]
        self.assertEqual(metrics.velocity(rows, today=self.TODAY)["tasks"], 2)

    def test_a_completion_outside_the_window_does_not(self):
        rows = [self.done("T-001", 3, 15), self.done("T-002", 3, 1)]
        rate = metrics.velocity(rows, today=self.TODAY)
        self.assertEqual(rate["tasks"], 1)
        self.assertEqual(rate["points"], 3)

    def test_the_window_is_reported_with_the_number(self):
        rate = metrics.velocity([], window_days=30, today=self.TODAY)
        self.assertEqual(rate["window_days"], 30)
        self.assertEqual(rate["to"], "2026-09-04")
        self.assertEqual(rate["from"], "2026-08-05")

    def test_an_estimated_effort_marks_the_rate_derived(self):
        rows = [self.done("T-001", 5, 3, effort_source="estimated"), self.done("T-002", 5, 4)]
        self.assertTrue(metrics.velocity(rows, today=self.TODAY)["derived"])

    def test_an_inferred_completion_date_marks_the_rate_derived(self):
        rows = [self.done("T-001", 5, 3, completed_source="inferred-git"), self.done("T-002", 5, 4)]
        self.assertTrue(metrics.velocity(rows, today=self.TODAY)["derived"])

    def test_recorded_figures_are_not_marked_derived(self):
        rows = [self.done("T-001", 5, 3), self.done("T-002", 5, 4)]
        self.assertFalse(metrics.velocity(rows, today=self.TODAY)["derived"])


class TestForecast(RateFixture):
    def test_remaining_points_exclude_completed_work(self):
        rows = [self.done("T-001", 5, 3), self.done("T-002", 9, 4), task_row(id="T-003", effort=8)]
        got = metrics.forecast(rows, today=self.TODAY)
        self.assertEqual(got["remaining_points"], 8)
        self.assertEqual(got["remaining_tasks"], 1)

    def test_a_projection_divides_remaining_points_by_the_rate(self):
        rows = [self.done("T-001", 5, 3), self.done("T-002", 9, 4), task_row(id="T-003", effort=14)]
        got = metrics.forecast(rows, today=self.TODAY)
        self.assertEqual(got["points_per_week"], 7.0)
        self.assertEqual(got["weeks_remaining"], 2.0)
        self.assertEqual(got["projected_date"], "2026-09-18")

    def test_too_few_completions_yields_no_date_and_no_zero(self):
        """The refusal is the point. Widening the window silently would move the
        basis of the figure without saying so."""
        rows = [self.done("T-001", 5, 3), task_row(id="T-002", effort=8)]
        got = metrics.forecast(rows, today=self.TODAY)
        self.assertFalse(got["sufficient"])
        self.assertIsNone(got["projected_date"])
        self.assertIsNone(got["weeks_remaining"])
        self.assertEqual(got["remaining_points"], 8)

    def test_the_window_is_not_widened_to_find_data(self):
        rows = [self.done("T-001", 5, 40), self.done("T-002", 5, 50), task_row(id="T-003", effort=8)]
        got = metrics.forecast(rows, today=self.TODAY)
        self.assertFalse(got["sufficient"])
        self.assertEqual(got["window_days"], 14)

    def test_unestimated_remaining_tasks_are_reported_not_ignored(self):
        rows = [
            self.done("T-001", 5, 3),
            self.done("T-002", 9, 4),
            task_row(id="T-003", effort=None),
        ]
        got = metrics.forecast(rows, today=self.TODAY)
        self.assertEqual(got["unestimated"], ["T-003"])
        self.assertEqual(got["remaining_points"], 0)

    def test_an_estimated_effort_in_the_backlog_marks_the_forecast_derived(self):
        rows = [
            self.done("T-001", 5, 3),
            self.done("T-002", 9, 4),
            task_row(id="T-003", effort=8, effort_source="estimated"),
        ]
        self.assertTrue(metrics.forecast(rows, today=self.TODAY)["derived"])

    def test_an_empty_backlog_projects_immediately(self):
        rows = [self.done("T-001", 5, 3), self.done("T-002", 9, 4)]
        got = metrics.forecast(rows, today=self.TODAY)
        self.assertEqual(got["remaining_points"], 0)
        self.assertEqual(got["weeks_remaining"], 0.0)
        self.assertEqual(got["projected_date"], "2026-09-04")


class TestRateInTheDocument(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".path"
        (self.root / "tasks").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_build_carries_the_rate_and_the_forecast(self):
        document = metrics.build(self.root)
        self.assertIn("velocity", document)
        self.assertIn("forecast", document)
        self.assertEqual(document["velocity"]["window_days"], metrics.DEFAULT_WINDOW_DAYS)


if __name__ == "__main__":
    unittest.main()
