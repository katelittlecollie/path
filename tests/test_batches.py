"""Tests for scripts/batches.py and the batch checks in scripts/check.py.

Each check test seeds the disagreement first and asserts that check finds it.
A batch splits one set of facts across two files — membership on the task,
order on the batch — so the check that they still agree is the one thing
holding that split together, and it has to be seen failing to be worth having.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import batches as batches_mod  # noqa: E402
import buildlog as buildlog_mod  # noqa: E402
import check as check_mod  # noqa: E402
import next as next_mod  # noqa: E402
import okf  # noqa: E402
import tasks as tasks_mod  # noqa: E402

AGENTS = """# Proj

## Current Task

None yet.

## Project Status

**Phase:** early
**Last updated:** 2026-07-16
"""


class TestDerivedStatus(unittest.TestCase):
    """F-54: a batch's status is a fact about its members, computed on read.

    The computation lives in scripts/next.py with the other pure derivations
    over frontmatter rows; scripts/batches.py owns the files and the commands.
    """

    def test_no_members_is_pending(self):
        self.assertEqual(next_mod.derived_status([]), "pending")

    def test_every_member_complete_is_complete(self):
        rows = [{"status": "complete"}, {"status": "complete"}]
        self.assertEqual(next_mod.derived_status(rows), "complete")

    def test_any_member_in_progress_is_in_progress(self):
        rows = [{"status": "pending"}, {"status": "in-progress"}]
        self.assertEqual(next_mod.derived_status(rows), "in-progress")

    def test_in_progress_outranks_blocked(self):
        """A batch with work under way is moving, even with a stuck member.

        Reversing these two would report a stalled batch for every batch that
        has one blocked task in it, which is most of them at some point.
        """
        rows = [{"status": "blocked"}, {"status": "in-progress"}]
        self.assertEqual(next_mod.derived_status(rows), "in-progress")

    def test_blocked_with_nothing_moving_is_blocked(self):
        rows = [{"status": "blocked"}, {"status": "pending"}]
        self.assertEqual(next_mod.derived_status(rows), "blocked")

    def test_all_pending_is_pending(self):
        self.assertEqual(next_mod.derived_status([{"status": "pending"}]), "pending")

    def test_completed_date_is_the_last_member_to_finish(self):
        rows = [
            {"status": "complete", "completed": "2026-07-14"},
            {"status": "complete", "completed": "2026-07-16"},
        ]
        self.assertEqual(next_mod.derived_completed(rows), "2026-07-16")

    def test_an_unfinished_batch_has_no_completion_date(self):
        rows = [{"status": "complete", "completed": "2026-07-14"}, {"status": "pending"}]
        self.assertIsNone(next_mod.derived_completed(rows))


class TestMembersAndRollup(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"id": "T-001", "batch": "B-001", "status": "complete", "effort": 3},
            {"id": "T-002", "batch": "B-001", "status": "pending", "effort": 5},
            {"id": "T-003", "batch": None, "status": "pending", "effort": 8},
        ]

    def test_members_follow_the_batch_sequence(self):
        got = next_mod.members(self.rows, "B-001", ["T-002", "T-001"])
        self.assertEqual([r["id"] for r in got], ["T-002", "T-001"])

    def test_a_member_missing_from_the_sequence_is_appended_not_dropped(self):
        """check reports the disagreement; hiding it here would make the report
        the only place a real task ever appears."""
        got = next_mod.members(self.rows, "B-001", ["T-002"])
        self.assertEqual([r["id"] for r in got], ["T-002", "T-001"])

    def test_unbatched_tasks_are_not_members(self):
        got = next_mod.members(self.rows, "B-001", [])
        self.assertNotIn("T-003", [r["id"] for r in got])

    def test_rollup_counts_tasks_and_points(self):
        batch = {"id": "B-001", "_title": "First", "sequence": ["T-001", "T-002"]}
        got = next_mod.rollup(self.rows, batch)
        self.assertEqual(got["tasks_done"], 1)
        self.assertEqual(got["tasks_total"], 2)
        self.assertEqual(got["points_done"], 3)
        self.assertEqual(got["points_total"], 8)
        self.assertEqual(got["status"], "pending")

    def test_rollup_ignores_a_member_with_no_effort_estimate(self):
        rows = self.rows + [{"id": "T-004", "batch": "B-001", "status": "pending"}]
        batch = {"id": "B-001", "_title": "First", "sequence": []}
        got = next_mod.rollup(rows, batch)
        self.assertEqual(got["tasks_total"], 3)
        self.assertEqual(got["points_total"], 8)


class BatchProjectFixture(unittest.TestCase):
    """A real project on disk, built through the commands rather than by hand."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".path"
        for directory in ("tasks", "requirements", "blueprints", "build-log"):
            (self.root / directory).mkdir(parents=True)
        (self.tmp / "AGENTS.md").write_text(AGENTS)
        (self.root / "requirements" / "03-functional.md").write_text(
            "---\ntype: Requirement\ntitle: Functional\n---\n\n**F-01** It must exist.\n"
        )
        shutil.copy(
            Path(__file__).resolve().parents[1] / "tasks" / "TASK-TEMPLATE.md",
            self.root / "tasks" / "TASK-TEMPLATE.md",
        )
        shutil.copy(
            Path(__file__).resolve().parents[1] / "tasks" / "BATCH-TEMPLATE.md",
            self.root / "tasks" / "BATCH-TEMPLATE.md",
        )
        self.new_task("one", 3)
        self.new_task("two", 5)
        self.batch = self.new_batch("first batch")

    # The shipped template leaves placeholders and links to blueprints this
    # fixture does not have, both of which `check` correctly rejects. Tasks here
    # need a body that is already filled in, or no batch could ever pass.
    CLEAN_BODY = (
        "\n# Do the thing\n\n## Objective\n\nMake the thing exist.\n\n"
        "## Tasks\n\n- [x] Do it\n\n## Acceptance Criteria\n\n- [x] It is done\n"
    )

    CLEAN_BATCH_BODY = "\n# First batch\n\n## Goal\n\nShip the thing.\n"

    def new_task(self, title, effort):
        path = tasks_mod.new_task(self.root, title, effort=effort)
        doc = okf.load(path)
        doc.body = self.CLEAN_BODY
        okf.save(doc)
        return path

    def new_batch(self, title):
        path = batches_mod.new_batch(self.root, title)
        doc = okf.load(path)
        doc.body = self.CLEAN_BATCH_BODY
        okf.save(doc)
        return path

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def messages(self):
        _, findings = check_mod.run(self.root, write_proof=False)
        return " | ".join(f.message for f in findings)

    def meta(self, path):
        return okf.load(path).path_meta


class TestBatchCommands(BatchProjectFixture):
    def test_new_batch_writes_no_derived_fields(self):
        meta = self.meta(self.batch)
        self.assertEqual(meta["id"], "B-001")
        self.assertEqual(meta["sequence"], [])
        self.assertNotIn("status", meta)
        self.assertNotIn("completed", meta)

    def test_add_sets_membership_and_appends_to_the_sequence(self):
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])
        self.assertEqual(self.meta(self.batch)["sequence"], ["T-001", "T-002"])
        self.assertEqual(self.meta(tasks_mod.find_task(self.root, "T-001"))["batch"], "B-001")

    def test_add_is_idempotent(self):
        batches_mod.add(self.root, "B-001", ["T-001"])
        batches_mod.add(self.root, "B-001", ["T-001"])
        self.assertEqual(self.meta(self.batch)["sequence"], ["T-001"])

    def test_a_task_belongs_to_at_most_one_batch(self):
        self.new_batch("second batch")
        batches_mod.add(self.root, "B-001", ["T-001"])
        with self.assertRaises(tasks_mod.TaskError) as caught:
            batches_mod.add(self.root, "B-002", ["T-001"])
        self.assertIn("already belongs to B-001", str(caught.exception))

    def test_remove_clears_membership_and_the_sequence(self):
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])
        batches_mod.remove(self.root, "B-001", ["T-001"])
        self.assertEqual(self.meta(self.batch)["sequence"], ["T-002"])
        self.assertIsNone(self.meta(tasks_mod.find_task(self.root, "T-001"))["batch"])

    def test_order_rewrites_the_sequence(self):
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])
        batches_mod.order(self.root, "B-001", ["T-002", "T-001"])
        self.assertEqual(self.meta(self.batch)["sequence"], ["T-002", "T-001"])

    def test_order_refuses_to_omit_a_member(self):
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])
        with self.assertRaises(tasks_mod.TaskError) as caught:
            batches_mod.order(self.root, "B-001", ["T-002"])
        self.assertIn("omits T-001", str(caught.exception))

    def test_order_refuses_to_invent_a_member(self):
        batches_mod.add(self.root, "B-001", ["T-001"])
        with self.assertRaises(tasks_mod.TaskError) as caught:
            batches_mod.order(self.root, "B-001", ["T-001", "T-002"])
        self.assertIn("not in the batch", str(caught.exception))

    def test_order_refuses_a_duplicate(self):
        batches_mod.add(self.root, "B-001", ["T-001"])
        with self.assertRaises(tasks_mod.TaskError) as caught:
            batches_mod.order(self.root, "B-001", ["T-001", "T-001"])
        self.assertIn("more than once", str(caught.exception))

    def test_a_refused_order_changes_nothing(self):
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])
        before = self.batch.read_text()
        with self.assertRaises(tasks_mod.TaskError):
            batches_mod.order(self.root, "B-001", ["T-002"])
        self.assertEqual(self.batch.read_text(), before)

    def test_unknown_batch_is_reported(self):
        with self.assertRaises(tasks_mod.TaskError) as caught:
            batches_mod.add(self.root, "B-009", ["T-001"])
        self.assertIn("no batch B-009", str(caught.exception))


class TestBatchIdentifiers(BatchProjectFixture):
    def test_batch_ids_have_their_own_sequence(self):
        self.assertEqual(tasks_mod.next_id(self.root, "B"), "B-002")
        self.assertEqual(tasks_mod.next_id(self.root, "T"), "T-003")

    def test_a_batch_id_named_only_in_the_build_log_is_never_reused(self):
        """F-36's rule, applied to batches: the log has to stay trustworthy."""
        self.batch.unlink()
        (self.root / "build-log" / "2026-07-16-note.md").write_text(
            "---\ntype: Build Log Entry\ntitle: note\n---\n\nB-001 was abandoned.\n"
        )
        self.assertEqual(tasks_mod.next_id(self.root, "B"), "B-002")

    def test_a_batch_id_nothing_refers_to_may_be_reused(self):
        self.batch.unlink()
        self.assertEqual(tasks_mod.next_id(self.root, "B"), "B-001")


class TestBatchChecks(BatchProjectFixture):
    """Every one of these seeds the defect and asserts check catches it."""

    def setUp(self):
        super().setUp()
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])

    def mutate_batch(self, old, new):
        self.batch.write_text(self.batch.read_text().replace(old, new))

    def test_sequence_omitting_a_claiming_task_fails(self):
        self.mutate_batch("sequence: [T-001, T-002]", "sequence: [T-002]")
        self.assertIn("omits T-001", self.messages())

    def test_sequence_naming_a_task_that_does_not_exist_fails(self):
        self.mutate_batch("sequence: [T-001, T-002]", "sequence: [T-001, T-002, T-009]")
        self.assertIn("T-009 does not exist", self.messages())

    def test_sequence_naming_a_task_that_does_not_claim_membership_fails(self):
        path = tasks_mod.find_task(self.root, "T-001")
        path.write_text(path.read_text().replace("batch: B-001", "batch:"))
        self.assertIn("do not have path.batch set to B-001", self.messages())

    def test_sequence_naming_the_same_task_twice_fails(self):
        self.mutate_batch("sequence: [T-001, T-002]", "sequence: [T-001, T-002, T-002]")
        self.assertIn("more than once", self.messages())

    def test_a_stored_batch_status_fails(self):
        self.mutate_batch("  sequence:", "  status: pending\n  sequence:")
        self.assertIn("derived from the batch's members", self.messages())

    def test_a_stored_batch_completion_date_fails(self):
        self.mutate_batch("  sequence:", "  completed: 2026-07-16\n  sequence:")
        self.assertIn("derived from the batch's members", self.messages())

    def test_a_batch_id_that_does_not_match_its_filename_fails(self):
        self.mutate_batch("id: B-001", "id: B-002")
        self.assertIn("does not match filename", self.messages())

    def test_a_wrong_type_fails(self):
        self.mutate_batch("type: Batch", "type: Task")
        self.assertIn("expected 'Batch'", self.messages())

    def test_updated_before_created_fails(self):
        doc = okf.load(self.batch)
        doc.path_meta["created"] = "2099-01-01"
        okf.save(doc)
        self.assertIn("is before path.created", self.messages())

    def test_a_task_pointing_at_a_batch_that_does_not_exist_fails(self):
        path = tasks_mod.find_task(self.root, "T-001")
        path.write_text(path.read_text().replace("batch: B-001", "batch: B-009"))
        self.assertIn("path.batch: B-009 does not exist", self.messages())

    def test_a_malformed_batch_id_on_a_task_fails(self):
        path = tasks_mod.find_task(self.root, "T-001")
        path.write_text(path.read_text().replace("batch: B-001", "batch: nonsense"))
        self.assertIn("path.batch must be B-NNN", self.messages())


class TestNoFalsePositives(BatchProjectFixture):
    def test_an_unbatched_task_is_unaffected(self):
        """The ordinary case: most tasks are in no batch and must stay silent."""
        self.assertNotIn("batch", self.messages())

    def test_a_null_batch_is_not_a_missing_batch(self):
        path = tasks_mod.find_task(self.root, "T-001")
        self.assertIsNone(self.meta(path)["batch"])
        self.assertNotIn("path.batch", self.messages())

    def test_a_consistent_batch_reports_nothing_about_sequence(self):
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])
        self.assertNotIn("sequence", self.messages())

    def test_checking_one_task_does_not_report_a_batch(self):
        """A single-task run must not fail on a file the caller did not ask about."""
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])
        self.batch.write_text(
            self.batch.read_text().replace("sequence: [T-001, T-002]", "sequence: [T-002]")
        )
        _, findings = check_mod.run(self.root, task_id="T-001", write_proof=False)
        self.assertNotIn("sequence", " | ".join(f.message for f in findings))


class TestBatchTransitions(BatchProjectFixture):
    def setUp(self):
        super().setUp()
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])

    def status(self, task_id):
        return self.meta(tasks_mod.find_task(self.root, task_id))["status"]

    def test_start_moves_every_pending_member(self):
        batches_mod.start(self.root, "B-001")
        self.assertEqual(self.status("T-001"), "in-progress")
        self.assertEqual(self.status("T-002"), "in-progress")

    def test_start_leaves_a_member_already_under_way_alone(self):
        tasks_mod.transition(self.root, "T-001", "in-progress")
        moved = batches_mod.start(self.root, "B-001")
        self.assertEqual(moved, [("T-002", "in-progress")])

    def test_complete_refuses_a_member_that_was_never_started(self):
        """The rule TRANSITIONS enforces one task at a time still applies to
        eight of them at once; batching the bookkeeping does not batch it away."""
        tasks_mod.transition(self.root, "T-001", "in-progress")
        with self.assertRaises(tasks_mod.TaskError) as caught:
            batches_mod.complete(self.root, "B-001")
        self.assertIn("T-002 is 'pending'", str(caught.exception))

    def test_a_refused_completion_changes_nothing(self):
        tasks_mod.transition(self.root, "T-001", "in-progress")
        with self.assertRaises(tasks_mod.TaskError):
            batches_mod.complete(self.root, "B-001")
        self.assertEqual(self.status("T-001"), "in-progress")
        self.assertIsNone(self.meta(tasks_mod.find_task(self.root, "T-001"))["completed"])

    def test_complete_stamps_every_member(self):
        batches_mod.start(self.root, "B-001")
        batches_mod.complete(self.root, "B-001", by="claude-opus-5")
        for task_id in ("T-001", "T-002"):
            meta = self.meta(tasks_mod.find_task(self.root, task_id))
            self.assertEqual(meta["status"], "complete")
            self.assertIsNotNone(meta["completed"])
            self.assertIn("claude-opus-5", meta["completed_by"])

    def test_complete_skips_a_member_already_complete(self):
        batches_mod.start(self.root, "B-001")
        tasks_mod.transition(self.root, "T-001", "complete")
        moved = batches_mod.complete(self.root, "B-001")
        self.assertEqual(moved, [("T-002", "complete")])

    def test_a_blocked_member_refuses_completion(self):
        tasks_mod.transition(self.root, "T-001", "in-progress")
        tasks_mod.transition(self.root, "T-002", "blocked")
        with self.assertRaises(tasks_mod.TaskError) as caught:
            batches_mod.complete(self.root, "B-001")
        self.assertIn("blocked", str(caught.exception))

    def test_an_empty_batch_cannot_be_completed(self):
        self.new_batch("empty")
        with self.assertRaises(tasks_mod.TaskError) as caught:
            batches_mod.complete(self.root, "B-002")
        self.assertIn("no members", str(caught.exception))


class TestBatchScopedCheck(BatchProjectFixture):
    def setUp(self):
        super().setUp()
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])
        self.new_task("outsider", 3)

    def run_batch(self, write_proof=False):
        return check_mod.run(self.root, batch_id="B-001", write_proof=write_proof)

    def test_a_batch_run_covers_every_member(self):
        path = tasks_mod.find_task(self.root, "T-002")
        path.write_text(path.read_text().replace("effort: 5", "effort: 4"))
        _, findings = self.run_batch()
        self.assertIn("T-002", " | ".join(f.where for f in findings))

    def test_a_batch_run_ignores_a_task_outside_the_batch(self):
        path = tasks_mod.find_task(self.root, "T-003")
        path.write_text(path.read_text().replace("effort: 3", "effort: 4"))
        _, findings = self.run_batch()
        self.assertNotIn("T-003", " | ".join(f.where for f in findings))

    def test_an_unknown_batch_is_reported(self):
        _, findings = check_mod.run(self.root, batch_id="B-009", write_proof=False)
        self.assertIn("no batch B-009", " | ".join(f.message for f in findings))

    def test_proof_is_written_on_every_member_of_a_passing_batch(self):
        for task_id in ("T-001", "T-002"):
            self.assertIsNone(self.meta(tasks_mod.find_task(self.root, task_id))["proof"]["result"])
        code, _ = self.run_batch(write_proof=True)
        self.assertEqual(code, 0)
        for task_id in ("T-001", "T-002"):
            proof = self.meta(tasks_mod.find_task(self.root, task_id))["proof"]
            self.assertEqual(proof["result"], "pass")

    def test_a_failing_batch_writes_proof_on_nobody(self):
        """All or nothing, the same rule a single task already has: a partially
        recorded pass would claim the batch was checked when it was not."""
        path = tasks_mod.find_task(self.root, "T-002")
        path.write_text(path.read_text().replace("effort: 5", "effort: 4"))
        code, _ = self.run_batch(write_proof=True)
        self.assertEqual(code, 1)
        for task_id in ("T-001", "T-002"):
            proof = self.meta(tasks_mod.find_task(self.root, task_id))["proof"]
            self.assertIsNone(proof["result"])


class TestRetrospectiveScaffold(BatchProjectFixture):
    def setUp(self):
        super().setUp()
        batches_mod.add(self.root, "B-001", ["T-001", "T-002"])
        batches_mod.start(self.root, "B-001")
        batches_mod.complete(self.root, "B-001")

    def test_one_entry_satisfies_every_member(self):
        """The whole bookkeeping claim, in one assertion."""
        buildlog_mod.write_retrospective(self.root, ["T-001", "T-002"], title="First batch")
        _, findings = check_mod.run(self.root, batch_id="B-001", write_proof=False)
        self.assertNotIn("RETROSPECTIVE", " | ".join(f.message for f in findings))

    def test_a_member_left_out_of_related_tasks_still_fails(self):
        """T-030's defect stays covered: prose is not the field check reads."""
        path = buildlog_mod.write_retrospective(self.root, ["T-001"], title="Partial")
        path.write_text(path.read_text() + "\n\nT-002 was in this batch too.\n")
        _, findings = check_mod.run(self.root, batch_id="B-001", write_proof=False)
        self.assertIn("no RETROSPECTIVE build log entry lists T-002", " | ".join(
            f.message for f in findings
        ))

    def test_the_entry_declares_its_type_in_frontmatter(self):
        path = buildlog_mod.write_retrospective(self.root, ["T-001"], title="First batch")
        meta = okf.load(path).path_meta
        self.assertEqual(meta["entry_type"], "RETROSPECTIVE")
        self.assertEqual(meta["related_tasks"], ["T-001"])

    def test_the_entry_leaves_no_placeholder_the_checker_rejects(self):
        path = buildlog_mod.write_retrospective(self.root, ["T-001", "T-002"], title="First batch")
        _, findings = check_mod.run(self.root, write_proof=False)
        about_entry = [f for f in findings if path.name in f.where]
        self.assertEqual(about_entry, [], msg=[str(f) for f in about_entry])

    def test_a_second_entry_on_the_same_day_does_not_overwrite_the_first(self):
        first = buildlog_mod.write_retrospective(self.root, ["T-001"], title="First batch")
        second = buildlog_mod.write_retrospective(self.root, ["T-002"], title="First batch")
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file() and second.is_file())

    def test_an_entry_with_no_tasks_is_refused(self):
        with self.assertRaises(tasks_mod.TaskError):
            buildlog_mod.write_retrospective(self.root, [], title="Nothing")

    def test_the_build_log_index_is_rebuilt(self):
        buildlog_mod.write_retrospective(self.root, ["T-001"], title="First batch")
        index = (self.root / "build-log" / "index.md").read_text()
        self.assertIn("RETROSPECTIVE", index)


if __name__ == "__main__":
    unittest.main()
