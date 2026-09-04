"""Tests for the derived directory indexes — T-027.

`tasks/index.md` and `build-log/index.md` are not documents anyone writes.
They are projections of the frontmatter in their directory, and the only
property that matters is that they cannot disagree with it. Before this,
three callers wrote them in three shapes and nothing rebuilt them after
scaffold time, so an index started drifting with the first task created and
`path check` had nothing to catch it with — index files are OKF-reserved and
carry no frontmatter, so there is no claim in them to validate.

What is defended here is that every mutation refreshes the projection, and
that a stale index is repaired rather than merely tolerated.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import init as init_mod  # noqa: E402
import okf  # noqa: E402
import tasks  # noqa: E402


class IndexFixture(unittest.TestCase):
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

    def index(self) -> str:
        return (self.root / "tasks" / "index.md").read_text(encoding="utf-8")

    def build_log_index(self) -> str:
        return (self.root / "build-log" / "index.md").read_text(encoding="utf-8")

    def write_entry(self, name: str, title: str, entry_type: str = "RETROSPECTIVE"):
        doc = okf.Doc(
            path=self.root / "build-log" / name,
            meta={
                "type": "Build Log Entry",
                "title": title,
                "description": "",
                "tags": [],
                "timestamp": "2026-08-21T00:00:00Z",
                "path": {"entry_type": entry_type, "date": "2026-08-21"},
            },
            body="\n# " + title + "\n",
        )
        okf.save(doc)


class TestCreationUpdatesTheIndex(IndexFixture):
    def test_new_task_appears(self):
        tasks.new_task(self.root, "First thing", effort=1)
        self.assertIn("T-001-first-thing.md", self.index())

    def test_new_task_carries_effort_and_title_under_its_state(self):
        """Status is the section heading now, not a word on the line."""
        tasks.new_task(self.root, "First thing", effort=1)
        body = self.index()
        self.assertIn("## Ready now", body)
        self.assertIn("1 pts — First thing", body)

    def test_second_task_does_not_displace_the_first(self):
        tasks.new_task(self.root, "First thing", effort=1)
        tasks.new_task(self.root, "Second thing", effort=1)
        body = self.index()
        self.assertIn("T-001-first-thing.md", body)
        self.assertIn("T-002-second-thing.md", body)

    def test_template_is_not_listed_as_a_task(self):
        tasks.new_task(self.root, "First thing", effort=1)
        self.assertNotIn("TASK-TEMPLATE.md", self.index())


class TestTransitionUpdatesTheIndex(IndexFixture):
    def section_of(self, filename):
        """Which heading a file is listed under, or None."""
        heading = None
        for line in self.index().splitlines():
            if line.startswith("## "):
                heading = line[3:]
            elif filename in line:
                return heading
        return None

    def test_status_change_moves_the_task_between_sections(self):
        tasks.new_task(self.root, "First thing", effort=1)
        self.assertEqual(self.section_of("T-001-first-thing.md"), "Ready now")
        tasks.transition(self.root, "T-001", "in-progress")
        self.assertEqual(self.section_of("T-001-first-thing.md"), "In progress")

    def test_completion_is_reflected(self):
        tasks.new_task(self.root, "First thing", effort=1)
        tasks.transition(self.root, "T-001", "in-progress")
        tasks.transition(self.root, "T-001", "complete")
        self.assertEqual(self.section_of("T-001-first-thing.md"), "Complete")


class TestOrdering(IndexFixture):
    def test_numeric_not_lexicographic(self):
        """T-010 must not sort above T-009 — the exact point at which a
        filename-sorted index stops being readable."""
        for n in range(1, 12):
            tasks.new_task(self.root, f"Thing number {n}", effort=1)

        lines = [ln for ln in self.index().splitlines() if ln.startswith("* [")]
        ids = [ln[3:8] for ln in lines]
        self.assertEqual(ids, sorted(ids, key=lambda s: int(s.split("-")[1])))
        self.assertLess(ids.index("T-009"), ids.index("T-010"))


class TestStaleIndexIsRepaired(IndexFixture):
    """The failure this task exists for: an index that exists but lies. The
    old heal fired only on a missing file, so this case was never touched."""

    def test_refresh_rewrites_a_stale_index(self):
        tasks.new_task(self.root, "First thing", effort=1)
        tasks.new_task(self.root, "Second thing", effort=1)
        (self.root / "tasks" / "index.md").write_text(
            "# stale — Tasks\n\n* [T-001-first-thing.md](T-001-first-thing.md) - pending — Wrong title\n",
            encoding="utf-8",
        )

        init_mod.refresh_project(self.root)
        body = self.index()
        self.assertIn("T-002-second-thing.md", body)
        self.assertNotIn("Wrong title", body)

    def test_refresh_reports_the_repair(self):
        tasks.new_task(self.root, "First thing", effort=1)
        (self.root / "tasks" / "index.md").write_text("# stale\n", encoding="utf-8")
        healed = init_mod.refresh_project(self.root)
        self.assertTrue(any("index.md" in h for h in healed), healed)

    def test_refresh_is_quiet_when_the_index_is_already_correct(self):
        tasks.new_task(self.root, "First thing", effort=1)
        init_mod.refresh_project(self.root)
        healed = init_mod.refresh_project(self.root)
        self.assertFalse([h for h in healed if "tasks/index.md" in h], healed)


class TestUnreadableFrontmatter(IndexFixture):
    """A malformed task must not take the whole index down with it, and must
    not vanish silently either — a quietly incomplete index that reads as
    authoritative is the failure mode this task removes."""

    def test_rest_of_the_index_still_writes(self):
        tasks.new_task(self.root, "Good thing", effort=1)
        (self.root / "tasks" / "T-999-broken.md").write_text(
            "---\nthis: is: not: valid: yaml:\n---\n\n# Broken\n", encoding="utf-8"
        )
        okf.rebuild_tasks_index(self.root / "tasks", "proj")
        self.assertIn("T-001-good-thing.md", self.index())

    def test_the_skip_is_reported(self):
        (self.root / "tasks" / "T-999-broken.md").write_text(
            "---\nthis: is: not: valid: yaml:\n---\n\n# Broken\n", encoding="utf-8"
        )
        unreadable = okf.rebuild_tasks_index(self.root / "tasks", "proj")
        self.assertEqual(unreadable, ["T-999-broken.md"])


class TestBuildLogIndex(IndexFixture):
    def test_entries_are_listed_with_type_and_title(self):
        self.write_entry("2026-08-21-t-001-retrospective.md", "T-001 Retrospective")
        okf.rebuild_build_log_index(self.root / "build-log", "proj")
        self.assertIn("2026-08-21-t-001-retrospective.md", self.build_log_index())
        self.assertIn("RETROSPECTIVE — T-001 Retrospective", self.build_log_index())

    def test_index_itself_is_never_listed(self):
        self.write_entry("2026-08-21-a.md", "A")
        okf.rebuild_build_log_index(self.root / "build-log", "proj")
        okf.rebuild_build_log_index(self.root / "build-log", "proj")
        self.assertNotIn("[index.md]", self.build_log_index())


class TestIndexIsNotAReferenceSource(IndexFixture):
    """F-36's residual case: an id nothing ever mentioned may be reused. A
    derived index must not be what keeps a number reserved, or the rebuild
    would quietly change how identifiers are allocated."""

    def test_deleted_unreferenced_task_frees_its_id(self):
        tasks.new_task(self.root, "First thing", effort=1)
        path = tasks.new_task(self.root, "Second thing", effort=1)
        path.unlink()
        self.assertEqual(tasks.next_id(self.root), "T-002")


class TestGroupedIndex(IndexFixture):
    """F-55: the file has to answer "what can I start" without running anything."""

    def index_files(self):
        return [
            line.split("](")[0].split("[")[1]
            for line in self.index().splitlines()
            if line.startswith("* [")
        ]

    def test_every_file_appears_exactly_once(self):
        for n, title in ((1, "First"), (2, "Second"), (3, "Third")):
            tasks.new_task(self.root, title, effort=1)
        tasks.transition(self.root, "T-002", "in-progress")
        tasks.transition(self.root, "T-003", "blocked")
        listed = self.index_files()
        self.assertEqual(sorted(listed), sorted(set(listed)))
        self.assertEqual(len(listed), 3)

    def test_a_waiting_task_names_what_it_waits_on(self):
        tasks.new_task(self.root, "First", effort=1)
        tasks.new_task(self.root, "Second", effort=1, requires=["T-001"])
        body = self.index()
        self.assertIn("## Waiting on prerequisites", body)
        self.assertIn("needs T-001", body)

    def test_a_startable_task_is_not_filed_as_waiting(self):
        """The defect the old identifier-ordered listing could not express."""
        tasks.new_task(self.root, "First", effort=1)
        tasks.new_task(self.root, "Second", effort=1, requires=["T-001"])
        tasks.transition(self.root, "T-001", "in-progress")
        tasks.transition(self.root, "T-001", "complete")
        self.assertIn("## Ready now", self.index())
        self.assertNotIn("## Waiting on prerequisites", self.index())

    def test_empty_sections_are_omitted(self):
        tasks.new_task(self.root, "First", effort=1)
        body = self.index()
        self.assertIn("## Ready now", body)
        for absent in ("## Blocked", "## Batches", "## Complete", "## In progress"):
            self.assertNotIn(absent, body)

    def test_the_index_carries_no_frontmatter(self):
        tasks.new_task(self.root, "First", effort=1)
        self.assertFalse(self.index().startswith("---"))

    def test_a_rebuild_is_idempotent(self):
        tasks.new_task(self.root, "First", effort=1)
        okf.rebuild_tasks_index(self.root / "tasks", "proj")
        once = self.index()
        okf.rebuild_tasks_index(self.root / "tasks", "proj")
        self.assertEqual(self.index(), once)

    def test_an_unreadable_task_is_reported_not_dropped_silently(self):
        tasks.new_task(self.root, "First", effort=1)
        broken = self.root / "tasks" / "T-002-broken.md"
        broken.write_text("---\nthis: [is not\n---\n\nbody\n")
        unreadable = okf.rebuild_tasks_index(self.root / "tasks", "proj")
        self.assertIn("T-002-broken.md", unreadable)


class TestBatchesInTheIndex(IndexFixture):
    def test_a_batch_is_listed_with_its_progress(self):
        import batches

        tasks.new_task(self.root, "First", effort=3)
        batches.new_batch(self.root, "A batch")
        batches.add(self.root, "B-001", ["T-001"])
        body = self.index()
        self.assertIn("## Batches", body)
        self.assertIn("B-001-a-batch.md", body)
        self.assertIn("0/1 tasks, 0/3 pts", body)

    def test_batch_membership_shows_on_the_task_line(self):
        import batches

        tasks.new_task(self.root, "First", effort=3)
        batches.new_batch(self.root, "A batch")
        batches.add(self.root, "B-001", ["T-001"])
        self.assertIn("3 pts · B-001 — First", self.index())

    def test_a_complete_batch_moves_out_of_the_live_section(self):
        import batches

        tasks.new_task(self.root, "First", effort=3)
        batches.new_batch(self.root, "A batch")
        batches.add(self.root, "B-001", ["T-001"])
        batches.start(self.root, "B-001")
        batches.complete(self.root, "B-001")
        body = self.index()
        self.assertIn("## Completed batches", body)
        self.assertNotIn("## Batches", body)


if __name__ == "__main__":
    unittest.main()
