"""Tests for scripts/decisions.py.

The interesting property is the one that isn't there: age is computed from
`raised` and `resolved` at read time and stored nowhere, so it cannot go stale.
"""

import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import decisions  # noqa: E402
import okf  # noqa: E402

TODAY = date.today().isoformat()


class DecisionFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".path"
        self.root.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp)


class TestRaise(DecisionFixture):
    def test_creates_the_log_on_first_use(self):
        self.assertFalse(decisions.log_path(self.root).exists())
        decisions.raise_decision(self.root, "Before or after?")
        doc = okf.load(decisions.log_path(self.root))
        self.assertEqual(doc.type, "Decision Log")

    def test_row_fields(self):
        decisions.raise_decision(self.root, "Before or after?", related_task="T-002")
        row = decisions.listing(self.root)[0]
        self.assertEqual(row["question"], "Before or after?")
        self.assertEqual(row["related_task"], "T-002")
        self.assertEqual(row["raised"], TODAY)
        self.assertIsNone(row["resolved"])
        self.assertIsNone(row["answer"])

    def test_numbers_increment(self):
        self.assertEqual(decisions.raise_decision(self.root, "One"), 1)
        self.assertEqual(decisions.raise_decision(self.root, "Two"), 2)

    def test_empty_question_refused(self):
        with self.assertRaises(decisions.DecisionError):
            decisions.raise_decision(self.root, "   ")

    def test_preamble_is_kept_in_the_body(self):
        """The prose explaining why this isn't a RAID log is reasoning, so it
        stays in the body rather than becoming a field."""
        decisions.raise_decision(self.root, "One")
        body = okf.load(decisions.log_path(self.root)).body
        self.assertIn("not a full RAID log", body)


class TestResolve(DecisionFixture):
    def setUp(self):
        super().setUp()
        decisions.raise_decision(self.root, "Before or after?")

    def test_resolve_sets_date_and_answer(self):
        decisions.resolve_decision(self.root, 1, "After.")
        row = decisions.listing(self.root)[0]
        self.assertEqual(row["resolved"], TODAY)
        self.assertEqual(row["answer"], "After.")

    def test_resolving_twice_is_refused(self):
        decisions.resolve_decision(self.root, 1, "After.")
        with self.assertRaises(decisions.DecisionError) as ctx:
            decisions.resolve_decision(self.root, 1, "Actually, before.")
        self.assertIn("already resolved", str(ctx.exception))

    def test_unknown_number_refused(self):
        with self.assertRaises(decisions.DecisionError):
            decisions.resolve_decision(self.root, 9, "x")

    def test_empty_answer_refused(self):
        with self.assertRaises(decisions.DecisionError):
            decisions.resolve_decision(self.root, 1, "  ")


class TestAge(unittest.TestCase):
    def test_open_decision_ages_against_today(self):
        raised = (date.today() - timedelta(days=12)).isoformat()
        self.assertEqual(decisions.age_days({"raised": raised, "resolved": None}), 12)

    def test_resolved_decision_ages_against_resolution(self):
        entry = {"raised": "2026-07-01", "resolved": "2026-07-09"}
        self.assertEqual(decisions.age_days(entry), 8)

    def test_age_is_never_stored(self):
        """The old table had an `Age (days)` column that the status page ignored
        and recomputed. A stored age starts going stale the moment it is written.

        Asserted against the frontmatter, not the whole file: the body's
        preamble talks *about* age, which is prose and entirely welcome.
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            root = tmp / ".path"
            root.mkdir()
            decisions.raise_decision(root, "One")
            row = okf.load(decisions.log_path(root)).path_meta["decisions"][0]
            self.assertEqual(set(row), {"question", "related_task", "raised", "resolved", "answer"})
        finally:
            shutil.rmtree(tmp)

    def test_malformed_dates_do_not_crash(self):
        self.assertIsNone(decisions.age_days({"raised": "whenever"}))
        self.assertIsNone(decisions.age_days({}))
        self.assertIsNone(decisions.age_days({"raised": "2026-07-01", "resolved": "soon"}))


class TestListing(DecisionFixture):
    def test_empty_when_no_log(self):
        self.assertEqual(decisions.listing(self.root), [])

    def test_unmigrated_log_yields_nothing_rather_than_raising(self):
        """Reporting is not validation. `path check` is what reports a
        non-conforming document; metrics dying on the first one would be a worse
        validator that also refuses to do its own job."""
        decisions.log_path(self.root).write_text(
            "# Decisions Log\n\n| Decision | Raised |\n|---|---|\n| Old format | 2026-07-01 |\n"
        )
        self.assertEqual(decisions.listing(self.root), [])

    def test_open_only_filter(self):
        decisions.raise_decision(self.root, "Open one")
        decisions.raise_decision(self.root, "Closed one")
        decisions.resolve_decision(self.root, 2, "Done.")
        self.assertEqual(len(decisions.listing(self.root)), 2)
        open_rows = decisions.listing(self.root, open_only=True)
        self.assertEqual(len(open_rows), 1)
        self.assertEqual(open_rows[0]["question"], "Open one")

    def test_numbers_are_stable_after_resolution(self):
        """Resolving a row must not renumber the others, or `resolve 2` starts
        pointing at a different question than it did a minute ago."""
        decisions.raise_decision(self.root, "One")
        decisions.raise_decision(self.root, "Two")
        decisions.resolve_decision(self.root, 1, "Answer.")
        self.assertEqual(decisions.listing(self.root)[1]["number"], 2)
        self.assertEqual(decisions.listing(self.root)[1]["question"], "Two")


if __name__ == "__main__":
    unittest.main()
