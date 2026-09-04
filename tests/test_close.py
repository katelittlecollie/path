"""Tests for scripts/close.py.

The property that matters most: the Judgment checklist in the generated entry
must come from the Definition of Done file itself, not a copy hard-coded here.
A second copy is a thing that drifts, and this is the one place in Path where
that lesson gets tested directly rather than just stated in a docstring.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import close as close_mod  # noqa: E402
import decisions as decisions_mod  # noqa: E402
import okf  # noqa: E402
import tasks as tasks_mod  # noqa: E402

DOD_SAMPLE = """---
type: Blueprint
title: Definition of Done
---

# Definition of Done

## Task Completion

- [ ] **[Mechanical]** Every item in the task's `## Tasks` section is checked off.
- [ ] **[Judgment]** The work has been reviewed by a human being.
- [ ] **[Judgment]** All new code compiles (or parses) without errors.

## Consistency

- [ ] **[Mechanical, partial]** Every task this one `requires` is itself complete.
- [ ] **[Judgment]** The work does not otherwise break or contradict prior work.
"""


class CloseFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "proj"
        self.root = self.project / ".path"
        for directory in ("tasks", "requirements", "blueprints", "build-log"):
            (self.root / directory).mkdir(parents=True)
        shutil.copy(
            Path(__file__).resolve().parents[1] / "tasks" / "TASK-TEMPLATE.md",
            self.root / "tasks" / "TASK-TEMPLATE.md",
        )
        (self.project / "AGENTS.md").write_text(
            "# Proj\n\n## Current Task\n\nT-001 (pending) — Thing\n"
        )

    def tearDown(self):
        shutil.rmtree(self.tmp)


class TestFindDod(CloseFixture):
    def test_finds_a_project_local_copy_by_filename_pattern(self):
        """Blueprint numbering is chosen per project (F-07) — lcm's is 04-,
        lcg's and Path's own are both 05-. Matched by name, not a fixed
        number."""
        (self.root / "blueprints" / "04-definition-of-done.md").write_text(DOD_SAMPLE)
        found = close_mod.find_dod(self.root)
        self.assertEqual(found.name, "04-definition-of-done.md")

    def test_falls_back_to_the_canonical_copy(self):
        found = close_mod.find_dod(self.root)
        self.assertIsNotNone(found)
        self.assertTrue(found.is_file())
        self.assertIn("Definition of Done", found.read_text())


class TestJudgmentItems(CloseFixture):
    def test_extracts_only_judgment_items(self):
        (self.root / "blueprints" / "05-definition-of-done.md").write_text(DOD_SAMPLE)
        items = close_mod.judgment_items(self.root)
        self.assertEqual(len(items), 3)
        self.assertTrue(all("reviewed" in i or "compiles" in i or "contradict" in i for i in items))

    def test_mechanical_items_are_excluded(self):
        (self.root / "blueprints" / "05-definition-of-done.md").write_text(DOD_SAMPLE)
        items = close_mod.judgment_items(self.root)
        self.assertFalse(any("checked off" in i for i in items))
        self.assertFalse(any("requires" in i for i in items))

    def test_a_new_judgment_item_appears_without_a_code_change(self):
        """The whole point of parsing rather than hard-coding: editing the DoD
        file is enough."""
        extended = DOD_SAMPLE + "\n- [ ] **[Judgment]** A brand new item nobody wrote code for.\n"
        (self.root / "blueprints" / "05-definition-of-done.md").write_text(extended)
        items = close_mod.judgment_items(self.root)
        self.assertTrue(any("brand new item" in i for i in items))


class TestCurrentTask(CloseFixture):
    def test_reads_the_task_id_from_agents_md(self):
        self.assertEqual(close_mod.current_task(self.root), "T-001")

    def test_none_when_agents_md_says_none_assigned(self):
        (self.project / "AGENTS.md").write_text(
            "# Proj\n\n## Current Task\n\nNone assigned.\n"
        )
        self.assertIsNone(close_mod.current_task(self.root))

    def test_none_when_agents_md_is_missing(self):
        (self.project / "AGENTS.md").unlink()
        self.assertIsNone(close_mod.current_task(self.root))

    def test_a_batch_line_reports_the_batch_not_a_member(self):
        """Found by running `path close` after completing B-003: the line read
        "B-003 complete — ... (T-114 through T-121)" and the first T-NNN won, so
        the entry named a finished task as the work in hand."""
        (self.project / "AGENTS.md").write_text(
            "# Proj\n\n## Current Task\n\n"
            "B-003 complete — Sequence, batching, and forecasting (T-114 through T-121).\n"
        )
        self.assertEqual(close_mod.current_task(self.root), "B-003")

    def test_a_task_line_mentioning_a_batch_second_still_reports_the_task(self):
        (self.project / "AGENTS.md").write_text(
            "# Proj\n\n## Current Task\n\nT-114 in-progress — first member of B-003.\n"
        )
        self.assertEqual(close_mod.current_task(self.root), "T-114")


class TestClose(CloseFixture):
    def test_writes_a_session_close_entry(self):
        path = close_mod.close(self.root, output=lambda *_: None)
        self.assertTrue(path.is_file())
        doc = okf.load(path)
        self.assertEqual(doc.type, "Build Log Entry")
        self.assertEqual(doc.path_meta["entry_type"], "SESSION-CLOSE")

    def test_regenerates_status_html(self):
        close_mod.close(self.root, output=lambda *_: None)
        self.assertTrue((self.root / "status.html").is_file())

    def test_embeds_the_mechanical_check_result(self):
        tasks_mod.new_task(self.root, "Clean task", effort=3)
        path = close_mod.close(self.root, output=lambda *_: None)
        text = path.read_text()
        self.assertIn("Mechanical Definition of Done Check", text)

    def test_embeds_the_judgment_checklist_from_the_dod_file(self):
        (self.root / "blueprints" / "05-definition-of-done.md").write_text(DOD_SAMPLE)
        path = close_mod.close(self.root, output=lambda *_: None)
        text = path.read_text()
        self.assertIn("The work has been reviewed by a human being.", text)
        self.assertNotIn("checked off.", text)  # the Mechanical item is excluded

    def test_second_close_same_day_gets_a_suffixed_filename(self):
        first = close_mod.close(self.root, output=lambda *_: None)
        second = close_mod.close(self.root, output=lambda *_: None)
        self.assertNotEqual(first, second)
        self.assertTrue(second.name.endswith("-2.md"))

    def test_blocked_task_appears_in_blockers(self):
        # AGENTS.md already mentions T-001, so next_id() — correctly — never
        # reuses it; capture whatever id is actually allocated.
        new_path = tasks_mod.new_task(self.root, "Stuck thing", effort=3)
        task_id = okf.load(new_path).path_meta["id"]
        tasks_mod.transition(self.root, task_id, "blocked")
        path = close_mod.close(self.root, output=lambda *_: None)
        self.assertIn(f"{task_id} is blocked", path.read_text())

    def test_open_decision_appears_in_blockers(self):
        decisions_mod.raise_decision(self.root, "Which way should this go?")
        path = close_mod.close(self.root, output=lambda *_: None)
        self.assertIn("Which way should this go?", path.read_text())

    def test_task_issue_appears_in_process_improvement_section(self):
        new_path = tasks_mod.new_task(self.root, "Thing", effort=3)
        task_id = okf.load(new_path).path_meta["id"]
        tasks_mod.log(self.root, "issue", task_id, "Found a broken thing")
        path = close_mod.close(self.root, output=lambda *_: None)
        text = path.read_text()
        self.assertIn(task_id, text)
        self.assertIn("Found a broken thing", text)

    def test_no_blockers_says_so_plainly(self):
        path = close_mod.close(self.root, output=lambda *_: None)
        self.assertIn("None.", path.read_text())

    def test_does_not_write_a_proof_as_a_side_effect(self):
        """close reports the mechanical check; it must not also silently
        stamp path.proof on every task the way `path check <id>` does."""
        path = tasks_mod.new_task(self.root, "Thing", effort=3)
        before = okf.load(path).path_meta.get("proof")
        close_mod.close(self.root, output=lambda *_: None)
        after = okf.load(path).path_meta.get("proof")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
