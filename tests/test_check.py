"""Tests for scripts/check.py — the proof of done.

Each test seeds a defect and asserts that check finds it. A validator that has
never been shown to fail is not evidence of anything, so the failing case comes
first everywhere here.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check as check_mod  # noqa: E402

GOOD_TASK = """---
type: Task
title: Do the thing
tags: [demo]
path:
  id: T-001
  status: pending
  effort: 3
  created: 2026-07-15
  updated: 2026-07-16
  completed: null
  implements: [F-01]
---

## Objective

Make the thing exist.
"""

AGENTS = """# Proj

## Current Task

T-001 (pending) — Do the thing

## Project Status

**Phase:** early
**Last updated:** 2026-07-16
"""

REQUIREMENTS = """---
type: Requirement
title: Functional
---

**F-01** The system must exist.
"""


class ProjectFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".path"
        for directory in ("tasks", "requirements", "blueprints", "build-log"):
            (self.root / directory).mkdir(parents=True)
        (self.tmp / "AGENTS.md").write_text(AGENTS)
        (self.root / "requirements" / "03-functional.md").write_text(REQUIREMENTS)
        self.task = self.root / "tasks" / "T-001-do-the-thing.md"
        self.task.write_text(GOOD_TASK)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def check(self, task_id="T-001", write_proof=False):
        return check_mod.run(self.root, task_id=task_id, write_proof=write_proof)

    def messages(self, **kwargs):
        _, findings = self.check(**kwargs)
        return " | ".join(f.message for f in findings)

    def mutate(self, old, new):
        self.task.write_text(self.task.read_text().replace(old, new))


class TestPasses(ProjectFixture):
    def test_clean_task_passes(self):
        code, findings = self.check()
        self.assertEqual(code, 0, msg=[str(f) for f in findings])
        self.assertEqual(findings, [])

    def test_unknown_task_id_fails(self):
        code, findings = self.check(task_id="T-999")
        self.assertEqual(code, 1)
        self.assertIn("no task T-999", findings[0].message)


class TestIdentity(ProjectFixture):
    def test_id_must_match_filename(self):
        self.mutate("id: T-001", "id: T-002")
        self.assertIn("does not match filename", self.messages())

    def test_id_must_be_well_formed(self):
        self.mutate("id: T-001", "id: nonsense")
        self.assertIn("path.id must be T-NNN", self.messages())

    def test_type_must_be_task(self):
        self.mutate("type: Task", "type: Blueprint")
        self.assertIn("expected 'Task'", self.messages())

    def test_missing_type_fails(self):
        self.task.write_text(GOOD_TASK.replace("type: Task\n", ""))
        self.assertIn("no non-empty `type`", self.messages())


class TestStatusAndEffort(ProjectFixture):
    def test_invalid_status(self):
        self.mutate("status: pending", "status: nearly-done")
        self.assertIn("path.status must be one of", self.messages())

    def test_effort_off_the_scale(self):
        self.mutate("effort: 3", "effort: 4")
        self.assertIn("Fibonacci", self.messages())

    def test_missing_effort(self):
        self.mutate("  effort: 3\n", "")
        self.assertIn("Fibonacci", self.messages())


class TestDates(ProjectFixture):
    def test_complete_without_completed_date(self):
        self.mutate("status: pending", "status: complete")
        self.assertIn("status is complete but path.completed is empty", self.messages())

    def test_completed_date_without_complete_status(self):
        self.mutate("completed: null", "completed: 2026-07-16")
        self.assertIn("path.completed is set", self.messages())

    def test_updated_before_created(self):
        self.mutate("updated: 2026-07-16", "updated: 2026-07-01")
        self.assertIn("is before path.created", self.messages())

    def test_malformed_date(self):
        self.mutate("created: 2026-07-15", "created: last Tuesday")
        self.assertIn("must be YYYY-MM-DD", self.messages())

    def test_missing_created(self):
        self.mutate("  created: 2026-07-15\n", "")
        self.assertIn("path.created is required", self.messages())


class TestTraceability(ProjectFixture):
    def test_implements_unknown_requirement(self):
        self.mutate("implements: [F-01]", "implements: [F-99]")
        self.assertIn("F-99 does not exist", self.messages())

    def test_implements_malformed_id(self):
        self.mutate("implements: [F-01]", "implements: [banana]")
        self.assertIn("is not a requirement id", self.messages())

    def test_requires_unknown_task(self):
        self.mutate("  implements: [F-01]", "  requires: [T-404]\n  implements: [F-01]")
        self.assertIn("T-404 does not exist", self.messages())

    def test_complete_task_with_incomplete_prerequisite(self):
        other = self.root / "tasks" / "T-002-other.md"
        other.write_text(GOOD_TASK.replace("id: T-001", "id: T-002"))
        (self.root / "build-log" / "r.md").write_text(
            "---\ntype: Build Log Entry\npath:\n"
            "  entry_type: RETROSPECTIVE\n"
            "  related_tasks: [T-001]\n"
            "---\n\n**Type:** RETROSPECTIVE\n\nT-001 done.\n"
        )
        self.mutate("  implements: [F-01]", "  requires: [T-002]\n  implements: [F-01]")
        self.mutate("status: pending", "status: complete")
        self.mutate("completed: null", "completed: 2026-07-16")
        self.assertIn("but this task is complete", self.messages())


class TestRetrospective(ProjectFixture):
    def complete_the_task(self):
        self.mutate("status: pending", "status: complete")
        self.mutate("completed: null", "completed: 2026-07-16")

    def write_retrospective(self, related: str, body: str = "went fine") -> None:
        (self.root / "build-log" / "2026-07-16-retro.md").write_text(
            "---\ntype: Build Log Entry\npath:\n"
            "  entry_type: RETROSPECTIVE\n"
            f"  related_tasks: [{related}]\n"
            f"---\n\n**Type:** RETROSPECTIVE\n\n{body}\n"
        )

    def test_complete_without_retrospective_fails(self):
        self.complete_the_task()
        self.assertIn("no RETROSPECTIVE build log entry", self.messages())

    def test_complete_with_retrospective_passes(self):
        self.complete_the_task()
        self.write_retrospective("T-001")
        code, findings = self.check()
        self.assertEqual(code, 0, msg=[str(f) for f in findings])

    def test_retrospective_listing_several_tasks_passes(self):
        self.complete_the_task()
        self.write_retrospective("T-077, T-001, T-099")
        code, findings = self.check()
        self.assertEqual(code, 0, msg=[str(f) for f in findings])

    def test_retrospective_for_a_different_task_does_not_count(self):
        self.complete_the_task()
        self.write_retrospective("T-077")
        self.assertIn("no RETROSPECTIVE build log entry", self.messages())

    def test_a_name_drop_in_the_prose_does_not_count(self):
        """The reason this check reads frontmatter. the sibling project's T-113 passed against
        T-110's retrospective, which names T-113 only to say it is out of scope
        there — the entry that mentions a task is not always the entry that
        closes it."""
        self.complete_the_task()
        self.write_retrospective(
            "T-077", body="Out of scope here: T-001, which is its own piece of work."
        )
        self.assertIn("no RETROSPECTIVE build log entry", self.messages())

    def test_an_entry_of_another_type_does_not_count(self):
        """A DECISION or CHANGE entry may legitimately list the task it belongs
        to; only a RETROSPECTIVE closes it."""
        self.complete_the_task()
        (self.root / "build-log" / "2026-07-16-decision.md").write_text(
            "---\ntype: Build Log Entry\npath:\n"
            "  entry_type: DECISION\n"
            "  related_tasks: [T-001]\n"
            "---\n\n**Type:** DECISION\n\nChose the simpler option.\n"
        )
        self.assertIn("no RETROSPECTIVE build log entry", self.messages())

    def test_an_unparseable_entry_is_skipped_not_fatal(self):
        """`build-log/index.md` has no frontmatter by design, and a malformed
        entry is check_document's finding to report, not this one's."""
        self.complete_the_task()
        (self.root / "build-log" / "index.md").write_text("# Index\n\nNo frontmatter here.\n")
        self.write_retrospective("T-001")
        code, findings = self.check()
        self.assertEqual(code, 0, msg=[str(f) for f in findings])


class TestBodyHygiene(ProjectFixture):
    def test_log_section_in_body_is_rejected(self):
        """F-30: the logs live in frontmatter only, or they drift."""
        self.task.write_text(GOOD_TASK + "\n## Drift Log\n\n- **2026-07-16** Type: correction\n")
        self.assertIn("belongs in frontmatter only", self.messages())

    def test_placeholder_marker_is_rejected(self):
        self.task.write_text(GOOD_TASK + "\nTODO: finish this.\n")
        self.assertIn("placeholder", self.messages())

    def test_unfilled_template_blank_is_rejected(self):
        self.task.write_text(GOOD_TASK + "\n[Short Descriptive Title]\n")
        self.assertIn("placeholder", self.messages())

    def test_a_marker_quoted_in_backticks_is_not_a_leftover(self):
        """lcm's T-001: "No `TODO`, `FIXME`, or placeholder comments in
        committed code" is an acceptance criterion, not an unfinished task."""
        self.task.write_text(
            GOOD_TASK + "\n- [x] No `TODO`, `FIXME`, or placeholder comments in committed code\n"
        )
        code, findings = self.check()
        self.assertEqual(code, 0, msg=[str(f) for f in findings])

    def test_prose_discussing_todos_is_not_a_leftover(self):
        """lcm's T-045 describes bare-TODO detection. A check that fails a
        document for discussing TODOs teaches people to ignore the check."""
        self.task.write_text(
            GOOD_TASK + "\nAdds bare-TODO detection (existing untagged TODOs are grandfathered).\n"
        )
        code, findings = self.check()
        self.assertEqual(code, 0, msg=[str(f) for f in findings])

    def test_broken_link_is_rejected(self):
        """OKF tolerates broken links; Path does not."""
        self.task.write_text(GOOD_TASK + "\nSee [nope](../blueprints/nope.md).\n")
        self.assertIn("broken link", self.messages())


class TestChecklistCompletion(ProjectFixture):
    """DoD: "every task in the task list is checked off" and "every
    acceptance criterion is met" are only partially mechanical — confirming a
    checked box's claim is actually true is judgment, but confirming no box
    was simply left unchecked is a fact this can verify."""

    def complete_the_task(self):
        self.mutate("status: pending", "status: complete")
        self.mutate("completed: null", "completed: 2026-07-16")
        (self.root / "build-log" / "2026-07-16-retro.md").write_text(
            "---\ntype: Build Log Entry\npath:\n"
            "  entry_type: RETROSPECTIVE\n"
            "  related_tasks: [T-001]\n"
            "---\n\n**Type:** RETROSPECTIVE\n\nT-001 went fine.\n"
        )

    def test_unchecked_task_box_fails_when_complete(self):
        self.task.write_text(
            self.task.read_text() + "\n## Tasks\n\n- [x] First\n- [ ] Second\n"
        )
        self.complete_the_task()
        self.assertIn("'## Tasks' has 1 unchecked box", self.messages())

    def test_unchecked_acceptance_criterion_fails_when_complete(self):
        self.task.write_text(
            self.task.read_text() + "\n## Acceptance Criteria\n\n- [ ] Works\n"
        )
        self.complete_the_task()
        self.assertIn("'## Acceptance Criteria' has 1 unchecked box", self.messages())

    def test_all_boxes_checked_passes(self):
        self.task.write_text(
            self.task.read_text() + "\n## Tasks\n\n- [x] First\n- [x] Second\n"
            "\n## Acceptance Criteria\n\n- [x] Works\n"
        )
        self.complete_the_task()
        code, findings = self.check()
        self.assertEqual(code, 0, msg=[str(f) for f in findings])

    def test_unchecked_box_in_an_unrelated_section_is_ignored(self):
        """Only the Tasks and Acceptance Criteria sections carry this
        obligation — a box left open in Notes, say, is not a completion
        claim at all."""
        self.task.write_text(
            self.task.read_text() + "\n## Notes\n\n- [ ] Maybe revisit this later\n"
        )
        self.complete_the_task()
        code, findings = self.check()
        self.assertEqual(code, 0, msg=[str(f) for f in findings])

    def test_unchecked_box_is_fine_while_still_in_progress(self):
        """An in-progress task legitimately has open boxes — only status:
        complete makes an unchecked box a defect."""
        self.task.write_text(
            self.task.read_text() + "\n## Tasks\n\n- [ ] Not done yet\n"
        )
        self.mutate("status: pending", "status: in-progress")
        code, findings = self.check()
        self.assertEqual(code, 0, msg=[str(f) for f in findings])

    def test_multiple_unchecked_boxes_are_counted(self):
        self.task.write_text(
            self.task.read_text() + "\n## Tasks\n\n- [ ] One\n- [ ] Two\n- [ ] Three\n"
        )
        self.complete_the_task()
        self.assertIn("has 3 unchecked boxes", self.messages())

    def test_working_link_is_accepted(self):
        self.task.write_text(GOOD_TASK + "\nSee [the requirement](../requirements/03-functional.md).\n")
        code, _ = self.check()
        self.assertEqual(code, 0)


class TestSecrets(ProjectFixture):
    def test_aws_key_is_caught(self):
        self.task.write_text(GOOD_TASK + "\nDeployed with AKIAIOSFODNN7EXAMPLE.\n")
        self.assertIn("AWS access key id", self.messages())

    def test_private_key_is_caught(self):
        self.task.write_text(GOOD_TASK + "\n-----BEGIN RSA PRIVATE KEY-----\n")
        self.assertIn("private key", self.messages())

    def test_hardcoded_credential_is_caught(self):
        self.task.write_text(GOOD_TASK + '\nSet password: "hunter2hunter2".\n')
        self.assertIn("hardcoded credential", self.messages())

    def test_ordinary_prose_is_not_flagged(self):
        self.task.write_text(GOOD_TASK + "\nThe password reset flow needs a token.\n")
        code, _ = self.check()
        self.assertEqual(code, 0)


class TestAgentsMd(ProjectFixture):
    def test_bloated_current_task_is_rejected(self):
        (self.tmp / "AGENTS.md").write_text(
            AGENTS.replace(
                "T-001 (pending) — Do the thing",
                "T-001 (pending) — Do the thing\nIt fixed the widget.\nAnd more narrative.",
            )
        )
        self.assertIn("'Current Task' is 3 lines", self.messages())

    def test_phase_prior_block_is_rejected(self):
        (self.tmp / "AGENTS.md").write_text(
            AGENTS.replace("**Phase:** early", "**Phase:** early\n**Phase (prior):** earlier")
        )
        self.assertIn("'Project Status' is 3 lines", self.messages())

    def test_missing_agents_md_is_rejected(self):
        (self.tmp / "AGENTS.md").unlink()
        self.assertIn("no AGENTS.md found", self.messages())


class TestProof(ProjectFixture):
    def test_proof_written_on_pass(self):
        code, _ = self.check(write_proof=True)
        self.assertEqual(code, 0)
        text = self.task.read_text()
        self.assertIn("result: pass", text)
        self.assertIn("checked_at:", text)

    def test_proof_not_written_on_failure(self):
        self.mutate("effort: 3", "effort: 4")
        code, _ = self.check(write_proof=True)
        self.assertEqual(code, 1)
        self.assertNotIn("result:", self.task.read_text())


if __name__ == "__main__":
    unittest.main()
