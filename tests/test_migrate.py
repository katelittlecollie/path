"""Tests for scripts/migrate.py.

Migration rewrites every documentation file in a project and is meant to run
once. That combination — high blast radius, no second chance to notice a bug in
production — is why the tests here lean on the destructive paths: what it
refuses to do, what it leaves alone, and what it reports rather than guesses.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import migrate  # noqa: E402
import okf  # noqa: E402

WORK_ORDER = """# WO-003 — Normalization Engine

---
**Status:** complete
**Created:** 2026-06-27
**Updated:** 2026-07-01
**Project:** lcg (Guardian)

---

## Objective

Do the thing.

## Change Log

- **2026-07-01** Status at time of change: in-progress — Widened the scope.

## Drift Log

- **2026-07-15** Type: post-completion-bug — Commit `abc1234` ("WO-009 complete") broke it. — Effort to correct: 1

## Issues Found During Execution

- **2026-06-30** Found a broken thing.

## Notes

See [WO-018](../work-orders/WO-018-web-ui-auth.md).
"""


class GitFixture(unittest.TestCase):
    """A real git repo: migration reads git history to infer completion dates."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "proj"
        self.root = self.project / ".path"
        for directory in ("work-orders", "requirements", "blueprints", "build-log"):
            (self.root / directory).mkdir(parents=True)

        (self.root / "work-orders" / "WO-003-normalizer.md").write_text(WORK_ORDER)
        (self.root / "requirements" / "01-overview.md").write_text("# Overview\n\nWhat it is.\n")
        (self.project / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\n## Current Work Order\n\nWO-003 — see path/work-orders/"
            "WO-003-normalizer.md\n"
        )
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.commit("initial")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.project, capture_output=True, text=True, check=False
        )

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


class TestRefusals(GitFixture):
    def test_apply_refuses_a_dirty_tree(self):
        """The undo is `git reset --hard`, which cannot tell your work from ours."""
        (self.project / "scratch.txt").write_text("uncommitted")
        with self.assertRaises(migrate.MigrationError) as ctx:
            migrate.migrate(self.project, apply=True)
        self.assertIn("uncommitted change", str(ctx.exception))

    def test_dry_run_allows_a_dirty_tree(self):
        """A dry run writes nothing, and a dirty tree is exactly when someone
        wants to see what migration would do before deciding how to clean up."""
        (self.project / "scratch.txt").write_text("uncommitted")
        report = migrate.migrate(self.project, apply=False)
        self.assertEqual(report.work_orders, 1)
        self.assertFalse((self.root / "tasks").exists())

    def test_refuses_outside_a_git_repo(self):
        loose = Path(tempfile.mkdtemp())
        try:
            (loose / ".path" / "blueprints").mkdir(parents=True)
            (loose / ".path" / "requirements").mkdir(parents=True)
            with self.assertRaises(migrate.MigrationError):
                migrate.migrate(loose, apply=False)
        finally:
            import shutil
            shutil.rmtree(loose)

    def test_refuses_an_already_migrated_project(self):
        migrate.migrate(self.project, apply=True)
        self.commit("migrated")
        with self.assertRaises(migrate.MigrationError) as ctx:
            migrate.migrate(self.project, apply=False)
        self.assertIn("already migrated", str(ctx.exception))

    def test_rejects_estimates_off_the_scale(self):
        path = self.tmp / "est.json"
        path.write_text('{"WO-003": 4}')
        with self.assertRaises(migrate.MigrationError):
            migrate.load_estimates(path)


class TestDryRun(GitFixture):
    def test_changes_nothing(self):
        before = sorted(p.name for p in (self.root / "work-orders").iterdir())
        report = migrate.migrate(self.project, apply=False)
        self.assertEqual(report.work_orders, 1)
        self.assertEqual(sorted(p.name for p in (self.root / "work-orders").iterdir()), before)
        self.assertFalse((self.root / "tasks").exists())
        self.assertEqual(self.git("status", "--porcelain").stdout.strip(), "")

    def test_reports_what_it_would_do(self):
        report = migrate.migrate(self.project, apply=False)
        self.assertIn(
            (".path/work-orders/WO-003-normalizer.md", ".path/tasks/T-003-normalizer.md"),
            report.renames,
        )


class TestConversion(GitFixture):
    def setUp(self):
        super().setUp()
        migrate.migrate(self.project, estimates={"WO-003": 5}, apply=True)
        self.task = self.root / "tasks" / "T-003-normalizer.md"

    def test_task_is_valid_okf(self):
        doc = okf.load(self.task)
        self.assertEqual(doc.type, "Task")
        self.assertEqual(doc.meta["title"], "Normalization Engine")

    def test_header_fields_become_frontmatter(self):
        meta = okf.load(self.task).path_meta
        self.assertEqual(meta["id"], "T-003")
        self.assertEqual(meta["status"], "complete")
        self.assertEqual(meta["created"], "2026-06-27")
        self.assertEqual(meta["migrated_from"], "WO-003")

    def test_estimate_is_applied_and_marked_derived(self):
        meta = okf.load(self.task).path_meta
        self.assertEqual(meta["effort"], 5)
        self.assertEqual(meta["effort_source"], "estimated")

    def test_completion_date_inferred_from_git_and_marked(self):
        meta = okf.load(self.task).path_meta
        self.assertIsNotNone(meta["completed"])
        self.assertEqual(meta["completed_source"], "inferred-git")

    def test_change_log_becomes_structured(self):
        entry = okf.load(self.task).path_meta["change_log"][0]
        self.assertEqual(entry["date"], "2026-07-01")
        self.assertEqual(entry["status_at_change"], "in-progress")
        self.assertEqual(entry["note"], "Widened the scope.")

    def test_drift_log_becomes_structured(self):
        entry = okf.load(self.task).path_meta["drift_log"][0]
        self.assertEqual(entry["kind"], "post-completion-bug")
        self.assertEqual(entry["effort_to_correct"], 1)

    def test_issues_become_structured(self):
        entry = okf.load(self.task).path_meta["issues"][0]
        self.assertEqual(entry["date"], "2026-06-30")

    def test_log_sections_leave_the_body(self):
        body = okf.load(self.task).body
        for heading in ("## Change Log", "## Drift Log", "## Issues Found"):
            self.assertNotIn(heading, body)

    def test_body_prose_survives(self):
        self.assertIn("Do the thing.", okf.load(self.task).body)

    def test_work_orders_directory_is_removed(self):
        self.assertFalse((self.root / "work-orders").exists())

    def test_template_is_replaced(self):
        self.assertTrue((self.root / "tasks" / "TASK-TEMPLATE.md").is_file())

    def test_index_is_written_without_frontmatter(self):
        """OKF reserves index.md and forbids frontmatter on it."""
        index = self.root / "tasks" / "index.md"
        self.assertTrue(index.is_file())
        self.assertIsNone(okf.split(index.read_text())[0])

    def test_per_project_scripts_are_gone(self):
        self.assertFalse((self.root / "scripts").exists())


class TestReferenceRewriting(GitFixture):
    def setUp(self):
        super().setUp()
        migrate.migrate(self.project, apply=True)
        self.task = self.root / "tasks" / "T-003-normalizer.md"

    def test_link_targets_are_rewritten(self):
        body = okf.load(self.task).body
        self.assertIn("../tasks/T-018-web-ui-auth.md", body)
        self.assertNotIn("work-orders/", body)

    def test_link_labels_follow_their_targets(self):
        """A link must not announce one id and lead to another."""
        self.assertIn("[T-018]", okf.load(self.task).body)

    def test_quoted_commit_message_is_left_alone(self):
        """The commit really does say "WO-009 complete". Rewriting a quotation
        would make the document cite a commit that never existed."""
        text = self.task.read_text()
        self.assertIn('("WO-009 complete")', text)

    def test_migrated_from_keeps_the_old_id(self):
        self.assertEqual(okf.load(self.task).path_meta["migrated_from"], "WO-003")


class TestLegacyPathPrefix(GitFixture):
    """A legacy project predates the dotfile convention entirely, so its own
    prose may still say bare `path/requirements/...`. Unlike a WO-009 mention
    inside a quoted commit message, this is a navigation pointer the project
    itself wrote, not a quotation of something external — so it gets updated,
    the same as any other link or filename."""

    def test_bare_prefix_becomes_dotted_in_agents_md(self):
        (self.project / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\nSee path/requirements/01-overview.md and "
            "path/blueprints/01-architecture.md for context.\n"
        )
        self.commit("legacy prefix")
        migrate.migrate(self.project, apply=True)
        text = (self.project / "AGENTS.md").read_text()
        self.assertIn(".path/requirements/01-overview.md", text)
        self.assertIn(".path/blueprints/01-architecture.md", text)
        self.assertNotIn(" path/requirements", text)

    def test_unrelated_use_of_the_word_path_is_untouched(self):
        """The regex is scoped to path/ immediately followed by one of Path's
        own subdirectory names — not a bare word boundary — precisely so a
        sentence that happens to use "path" is never touched."""
        (self.project / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\nThe import path/to/module resolution changed in WO-003.\n"
        )
        self.commit("unrelated path mention")
        migrate.migrate(self.project, apply=True)
        text = (self.project / "AGENTS.md").read_text()
        self.assertIn("path/to/module", text)

    def test_already_dotted_reference_is_not_double_dotted(self):
        (self.project / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\nSee .path/requirements/01-overview.md.\n"
        )
        self.commit("already correct")
        migrate.migrate(self.project, apply=True)
        text = (self.project / "AGENTS.md").read_text()
        self.assertIn(".path/requirements/01-overview.md", text)
        self.assertNotIn("..path/", text)


class TestAgentsMd(GitFixture):
    def setUp(self):
        super().setUp()
        migrate.migrate(self.project, apply=True)

    def test_agents_md_is_created(self):
        self.assertTrue((self.project / "AGENTS.md").is_file())

    def test_agents_md_uses_task_vocabulary(self):
        text = (self.project / "AGENTS.md").read_text()
        self.assertIn("Current Task", text)
        self.assertIn("path/tasks/T-003-normalizer.md", text)

    def test_every_case_of_work_order_is_retitled(self):
        """Spelling the variants out by hand missed sentence case — "Work order
        template", exactly how a nav table writes it."""
        (self.project / "AGENTS.md").unlink()
        (self.project / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\n"
            "| Work order template | x |\n"
            "A Work Order is a unit. Several work orders exist. The Work orders list.\n"
            "See the work-order template.\n"
        )
        self.commit("case variants")
        migrate.convert_agents_md(self.root, migrate.Report(), apply=True)
        text = (self.project / "AGENTS.md").read_text()
        self.assertNotIn("ork order", text)
        self.assertNotIn("ork Order", text)
        self.assertIn("Task template", text)
        self.assertIn("A Task is a unit", text)
        self.assertIn("Several tasks exist", text)

    def test_agents_md_points_at_the_global_profile(self):
        self.assertIn("$LCP_HOME", (self.project / "AGENTS.md").read_text())

    def test_claude_md_becomes_a_pointer(self):
        text = (self.project / "CLAUDE.md").read_text()
        self.assertIn("AGENTS.md", text)
        self.assertLess(len(text.splitlines()), 15)


class TestAvailableCommands(GitFixture):
    """Migration deletes path/scripts/. An Available Commands section still
    telling people to run them is broken instructions in the first file every
    agent reads — and both lcm and lcg had exactly that."""

    def test_section_stops_pointing_at_deleted_scripts(self):
        (self.project / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\n## Available Commands\n\n```bash\n"
            "./path/scripts/path-status.sh   # status\n```\n\n## Project Status\n\nPhase: early\n"
        )
        self.commit("with a commands section")
        migrate.migrate(self.project, apply=True)
        text = (self.project / "AGENTS.md").read_text()
        self.assertNotIn("path/scripts/path-status.sh", text)
        self.assertIn("path status", text)

    def test_following_sections_survive_the_replacement(self):
        (self.project / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\n## Available Commands\n\n`./path/scripts/path-status.sh`\n\n"
            "## Project Status\n\nPhase: early\n"
        )
        self.commit("with a commands section")
        migrate.migrate(self.project, apply=True)
        self.assertIn("## Project Status", (self.project / "AGENTS.md").read_text())


class TestOtherDocuments(GitFixture):
    def setUp(self):
        super().setUp()
        migrate.migrate(self.project, apply=True)

    def test_requirements_gain_frontmatter(self):
        doc = okf.load(self.root / "requirements" / "01-overview.md")
        self.assertEqual(doc.type, "Requirement")
        self.assertEqual(doc.meta["title"], "Overview")

    def test_existing_frontmatter_is_not_doubled(self):
        report = migrate.Report()
        path = self.root / "requirements" / "01-overview.md"
        self.assertIsNone(migrate.add_frontmatter(path, self.root, report))


class TestStatusNormalisation(GitFixture):
    def test_capital_complete_is_normalised(self):
        """Two lcm work orders say `Complete`. The old parser compared without
        normalising, so both were silently dropped from every metric."""
        path = self.root / "work-orders" / "WO-003-normalizer.md"
        path.write_text(WORK_ORDER.replace("**Status:** complete", "**Status:** Complete"))
        self.commit("capital")
        report = migrate.migrate(self.project, apply=True)
        self.assertEqual(okf.load(self.root / "tasks" / "T-003-normalizer.md").path_meta["status"],
                         "complete")
        self.assertTrue(any("normalised status" in n for n in report.notes))

    def test_unknown_status_warns_and_defaults(self):
        path = self.root / "work-orders" / "WO-003-normalizer.md"
        path.write_text(WORK_ORDER.replace("**Status:** complete", "**Status:** nearly"))
        self.commit("odd")
        report = migrate.migrate(self.project, apply=True)
        self.assertEqual(okf.load(self.root / "tasks" / "T-003-normalizer.md").path_meta["status"],
                         "pending")
        self.assertTrue(any("unrecognised status" in w for w in report.warnings))

    def test_missing_estimate_is_reported_not_guessed(self):
        report = migrate.migrate(self.project, apply=False)
        self.assertTrue(any("no effort estimate" in w for w in report.warnings))


class TestBuildLogRenaming(GitFixture):
    """Task filenames are WO-NNN-slug.md (uppercase); build-log filenames follow
    a different convention entirely — [YYYY-MM-DD]-[topic].md, lowercase — and a
    topic about a work order writes it lowercase: wo-001. That pattern was never
    matched by the uppercase-only rewrite, so a migrated project could end up
    with task T-001 next to a retrospective still named after WO-001."""

    def setUp(self):
        super().setUp()
        migrate.migrate(self.project, apply=True)
        build_log = self.root / "build-log"
        (build_log / "2026-06-27-wo-003-retrospective.md").write_text(
            "---\ntype: Build Log Entry\n---\n\nRETROSPECTIVE — T-003 done.\n"
        )
        (build_log / "2026-07-10-wo-018-architecture-change.md").write_text(
            "---\ntype: Build Log Entry\n---\n\n"
            "See [the retrospective](2026-06-27-wo-003-retrospective.md) and also "
            "`2026-06-27-wo-003-retrospective.md` in prose.\n"
        )
        (self.root / "tasks" / "T-018-web-ui-auth.md").write_text(
            "---\ntype: Task\npath:\n  id: T-018\n  status: pending\n  effort: 3\n---\n\n"
            "See [prior work](../build-log/2026-06-27-wo-003-retrospective.md).\n"
        )

    def test_files_are_renamed(self):
        renames = migrate.rename_build_log_files(self.root, migrate.Report(), apply=True)
        self.assertEqual(
            renames,
            {
                "2026-06-27-wo-003-retrospective.md": "2026-06-27-t-003-retrospective.md",
                "2026-07-10-wo-018-architecture-change.md": "2026-07-10-t-018-architecture-change.md",
            },
        )
        build_log = self.root / "build-log"
        self.assertTrue((build_log / "2026-06-27-t-003-retrospective.md").is_file())
        self.assertFalse((build_log / "2026-06-27-wo-003-retrospective.md").exists())

    def test_dry_run_renames_nothing(self):
        renames = migrate.rename_build_log_files(self.root, migrate.Report(), apply=False)
        self.assertEqual(len(renames), 2)
        self.assertTrue((self.root / "build-log" / "2026-06-27-wo-003-retrospective.md").is_file())

    def test_markdown_link_target_is_updated(self):
        renames = migrate.rename_build_log_files(self.root, migrate.Report(), apply=True)
        migrate.rewrite_build_log_references(self.root, renames, apply=True)
        text = (self.root / "build-log" / "2026-07-10-t-018-architecture-change.md").read_text()
        self.assertIn("(2026-06-27-t-003-retrospective.md)", text)
        self.assertNotIn("wo-003", text)

    def test_bare_backtick_mention_is_updated_too(self):
        """Not a markdown link, so `path check`'s link checker can't see it —
        but it's still a pointer to a real file, not a quotation, so it still
        needs fixing."""
        renames = migrate.rename_build_log_files(self.root, migrate.Report(), apply=True)
        migrate.rewrite_build_log_references(self.root, renames, apply=True)
        text = (self.root / "build-log" / "2026-07-10-t-018-architecture-change.md").read_text()
        self.assertIn("`2026-06-27-t-003-retrospective.md`", text)

    def test_cross_directory_link_from_a_task_is_updated(self):
        renames = migrate.rename_build_log_files(self.root, migrate.Report(), apply=True)
        migrate.rewrite_build_log_references(self.root, renames, apply=True)
        text = (self.root / "tasks" / "T-018-web-ui-auth.md").read_text()
        self.assertIn("../build-log/2026-06-27-t-003-retrospective.md", text)

    def test_renamed_files_resolve_under_path_check(self):
        import check

        renames = migrate.rename_build_log_files(self.root, migrate.Report(), apply=True)
        migrate.rewrite_build_log_references(self.root, renames, apply=True)
        checker = check.Checker(self.root)
        checker.check_task(
            self.root / "tasks" / "T-018-web-ui-auth.md", set(),
            {r["id"]: r for r in __import__("tasks").summary(self.root)},
        )
        broken_links = [f for f in checker.findings if "broken link" in f.message]
        self.assertEqual(broken_links, [], [str(f) for f in broken_links])

    def test_files_with_no_wo_number_are_untouched(self):
        build_log = self.root / "build-log"
        (build_log / "2026-07-01-plain-decision.md").write_text(
            "---\ntype: Build Log Entry\n---\n\nA decision with no WO reference.\n"
        )
        renames = migrate.rename_build_log_files(self.root, migrate.Report(), apply=True)
        self.assertNotIn("2026-07-01-plain-decision.md", renames)
        self.assertTrue((build_log / "2026-07-01-plain-decision.md").is_file())

    def test_no_renames_is_a_no_op(self):
        build_log = self.root / "build-log"
        for path in build_log.glob("*wo-*.md"):
            path.unlink()
        report = migrate.Report()
        self.assertEqual(migrate.rename_build_log_files(self.root, report, apply=True), {})
        self.assertEqual(report.renames, [])

    def test_wired_into_the_main_pipeline(self):
        """A fresh migration must not need the standalone repair at all."""
        second = self.tmp / "proj2"
        root2 = second / ".path"
        (root2 / "work-orders").mkdir(parents=True)
        (root2 / "build-log").mkdir()
        (root2 / "requirements").mkdir()
        (root2 / "blueprints").mkdir()
        (root2 / "work-orders" / "WO-007-thing.md").write_text(WORK_ORDER.replace("WO-003", "WO-007"))
        (root2 / "build-log" / "2026-07-01-wo-007-retrospective.md").write_text(
            "---\ntype: Build Log Entry\n---\n\nDone.\n"
        )
        subprocess.run(["git", "init", "-q"], cwd=second)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=second)
        subprocess.run(["git", "config", "user.name", "t"], cwd=second)
        subprocess.run(["git", "add", "-A"], cwd=second)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=second)

        migrate.migrate(second, apply=True)
        self.assertTrue((root2 / "build-log" / "2026-07-01-t-007-retrospective.md").is_file())
        self.assertFalse((root2 / "build-log" / "2026-07-01-wo-007-retrospective.md").exists())


class TestDecisions(GitFixture):
    def test_table_becomes_frontmatter_and_age_is_dropped(self):
        (self.root / "decisions-log.md").write_text(
            "# Decisions Log\n\nPreamble.\n\n"
            "| Decision | Related WO | Raised | Resolved | Age (days) |\n"
            "|---|---|---|---|---|\n"
            "| Before or after? | WO-003 | 2026-07-01 | 2026-07-05 | 4 |\n"
        )
        self.commit("decisions")
        migrate.migrate(self.project, apply=True)
        doc = okf.load(self.root / "decisions-log.md")
        row = doc.path_meta["decisions"][0]
        self.assertEqual(row["question"], "Before or after?")
        self.assertEqual(row["related_task"], "T-003")
        self.assertEqual(row["raised"], "2026-07-01")
        self.assertNotIn("age", row)
        self.assertNotIn("age_days", row)

    def test_template_placeholder_rows_are_skipped(self):
        """An unfilled template row is not a decision anyone ever raised."""
        (self.root / "decisions-log.md").write_text(
            "# Decisions Log\n\n"
            "| Decision | Related WO | Raised | Resolved | Age (days) |\n"
            "|---|---|---|---|---|\n"
            "| [One-line question] | [WO-NNN or —] | YYYY-MM-DD | YYYY-MM-DD or — | — |\n"
        )
        self.commit("template row")
        report = migrate.migrate(self.project, apply=True)
        self.assertEqual(report.decisions_migrated, 0)


if __name__ == "__main__":
    unittest.main()
