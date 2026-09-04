"""Tests for scripts/init.py.

Two things matter most: a fresh project must pass `path check` immediately
(zero tasks is a valid state — nobody should have to write a task before the
scaffold is considered sound), and refreshing an already-current project must
be a true no-op, not a set of files rewritten to the same content every time.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check as check_mod  # noqa: E402
import init as init_mod  # noqa: E402
import okf  # noqa: E402


class InitFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cwd = self.tmp / "myproject"
        self.cwd.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)


class TestIsInitialized(InitFixture):
    def test_false_for_an_empty_directory(self):
        self.assertFalse(init_mod.is_initialized(self.cwd))

    def test_true_after_init(self):
        init_mod.init_project(self.cwd)
        self.assertTrue(init_mod.is_initialized(self.cwd))


class TestInitProject(InitFixture):
    def test_creates_the_standard_layout(self):
        root, _ = init_mod.init_project(self.cwd)
        for directory in ("requirements", "blueprints", "tasks", "build-log"):
            self.assertTrue((root / directory).is_dir(), directory)
        self.assertTrue((self.cwd / "AGENTS.md").is_file())

    def test_does_not_create_decisions_log(self):
        """Optional per `path check`, and created lazily by decisions.py the
        moment `path decision raise` is actually used — never eagerly, or a
        plain project with no question to raise carries a permanently-empty
        file for no reason."""
        root, created = init_mod.init_project(self.cwd)
        self.assertFalse((root / "decisions-log.md").exists())
        self.assertNotIn(root / "decisions-log.md", created)

    def test_every_created_file_is_reported(self):
        root, created = init_mod.init_project(self.cwd)
        for path in created:
            self.assertTrue(path.is_file(), f"{path} reported created but does not exist")

    def test_requirement_and_blueprint_stubs_are_valid_okf(self):
        root, _ = init_mod.init_project(self.cwd)
        for path in (root / "requirements").glob("*.md"):
            doc = okf.load(path)
            self.assertEqual(doc.type, "Requirement")
        for path in (root / "blueprints").glob("*.md"):
            doc = okf.load(path)
            self.assertEqual(doc.type, "Blueprint")

    def test_task_template_matches_canonical(self):
        root, _ = init_mod.init_project(self.cwd)
        canonical = (init_mod.CANONICAL_ROOT / "tasks" / "TASK-TEMPLATE.md").read_text()
        self.assertEqual((root / "tasks" / "TASK-TEMPLATE.md").read_text(), canonical)

    def test_index_files_have_no_frontmatter(self):
        root, _ = init_mod.init_project(self.cwd)
        self.assertIsNone(okf.split((root / "tasks" / "index.md").read_text())[0])
        self.assertIsNone(okf.split((root / "build-log" / "index.md").read_text())[0])

    def test_agents_md_names_the_project(self):
        root, _ = init_mod.init_project(self.cwd)
        text = (self.cwd / "AGENTS.md").read_text()
        self.assertIn("myproject", text)

    def test_existing_agents_md_is_not_overwritten(self):
        (self.cwd / "AGENTS.md").write_text("# Hand-written, do not touch\n")
        init_mod.init_project(self.cwd)
        self.assertEqual((self.cwd / "AGENTS.md").read_text(), "# Hand-written, do not touch\n")

    def test_fresh_project_passes_path_check(self):
        """Zero tasks is a valid state — nobody should have to write a task
        before the scaffold itself is considered sound."""
        root, _ = init_mod.init_project(self.cwd)
        exit_code, findings = check_mod.run(root)
        self.assertEqual(exit_code, 0, [str(f) for f in findings])


class TestRefreshProject(InitFixture):
    def setUp(self):
        super().setUp()
        self.root, _ = init_mod.init_project(self.cwd)

    def test_freshly_initialized_project_needs_no_healing(self):
        self.assertEqual(init_mod.refresh_project(self.root), [])

    def test_missing_template_is_restored(self):
        (self.root / "tasks" / "TASK-TEMPLATE.md").unlink()
        healed = init_mod.refresh_project(self.root)
        self.assertIn(".path/tasks/TASK-TEMPLATE.md", healed)
        self.assertTrue((self.root / "tasks" / "TASK-TEMPLATE.md").is_file())

    def test_missing_tasks_index_is_restored(self):
        (self.root / "tasks" / "index.md").unlink()
        healed = init_mod.refresh_project(self.root)
        self.assertIn(".path/tasks/index.md", healed)

    def test_missing_build_log_index_is_restored(self):
        (self.root / "build-log" / "index.md").unlink()
        healed = init_mod.refresh_project(self.root)
        self.assertIn(".path/build-log/index.md", healed)

    def test_refresh_never_creates_a_decisions_log(self):
        """The real incident this guards against: an established project that
        predates this tooling and genuinely never had a decisions-log.md must
        not get a new tracked file the moment someone runs `path .` on it.
        Optional per `path check`; created lazily by `path decision raise`."""
        self.assertFalse((self.root / "decisions-log.md").exists())  # true after init already
        healed = init_mod.refresh_project(self.root)
        self.assertEqual(healed, [])
        self.assertFalse((self.root / "decisions-log.md").exists())

    def test_missing_agents_md_is_restored(self):
        (self.cwd / "AGENTS.md").unlink()
        healed = init_mod.refresh_project(self.root)
        self.assertIn("AGENTS.md", healed)

    def test_restored_agents_md_does_not_clobber_a_hand_edit(self):
        """Healing only fires when the file is genuinely missing — refresh
        must never silently overwrite content someone wrote."""
        (self.cwd / "AGENTS.md").write_text("# My real navigation notes\n")
        healed = init_mod.refresh_project(self.root)
        self.assertEqual(healed, [])
        self.assertEqual((self.cwd / "AGENTS.md").read_text(), "# My real navigation notes\n")

    def test_healing_does_not_touch_unrelated_files(self):
        marker = self.root / "requirements" / "01-overview.md"
        original = marker.read_text()
        (self.root / "tasks" / "index.md").unlink()
        init_mod.refresh_project(self.root)
        self.assertEqual(marker.read_text(), original)

    def test_healed_project_still_passes_check(self):
        (self.root / "tasks" / "TASK-TEMPLATE.md").unlink()
        (self.root / "tasks" / "index.md").unlink()
        init_mod.refresh_project(self.root)
        exit_code, findings = check_mod.run(self.root)
        self.assertEqual(exit_code, 0, [str(f) for f in findings])


if __name__ == "__main__":
    unittest.main()
