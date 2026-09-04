"""Tests for scripts/profile.py.

Two properties matter most here. Scaffolding must never overwrite a file the
owner has edited — the whole safety of "run this again any time" depends on
it. And a shim write must be a surgical insert into a marked block, never a
touch of anything else already in that file, because these are the owner's own
global config files, not Path's to rewrite.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import profile as profile_mod  # noqa: E402


class ProfileFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.lcp_home = self.tmp / "lcp"

    def tearDown(self):
        shutil.rmtree(self.tmp)


class TestHome(unittest.TestCase):
    def test_explicit_override_wins(self):
        self.assertEqual(profile_mod.home("/custom/path"), Path("/custom/path"))

    def test_env_var_used_when_no_override(self, ):
        import os
        old = os.environ.get("LCP_HOME")
        try:
            os.environ["LCP_HOME"] = "/from/env"
            self.assertEqual(profile_mod.home(None), Path("/from/env"))
        finally:
            if old is None:
                os.environ.pop("LCP_HOME", None)
            else:
                os.environ["LCP_HOME"] = old

    def test_default_is_dot_lcp(self):
        import os
        old = os.environ.pop("LCP_HOME", None)
        try:
            self.assertEqual(profile_mod.home(None), Path.home() / ".lcp")
        finally:
            if old is not None:
                os.environ["LCP_HOME"] = old


class TestScaffold(ProfileFixture):
    def test_creates_expected_structure(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        self.assertTrue((self.lcp_home / "config.yml").is_file())
        self.assertTrue((self.lcp_home / "profile" / "index.md").is_file())
        for name in profile_mod.PROFILE_DOC_ORDER:
            self.assertTrue((self.lcp_home / "profile" / name).is_file(), name)
        self.assertTrue((self.lcp_home / "state" / "graphify").is_dir())

    def test_index_has_no_frontmatter(self):
        """OKF reserves index.md and forbids frontmatter on it."""
        profile_mod.ensure_scaffold(self.lcp_home)
        text = (self.lcp_home / "profile" / "index.md").read_text()
        self.assertFalse(text.startswith("---"))

    def test_seed_docs_are_valid_okf(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import okf

        profile_mod.ensure_scaffold(self.lcp_home)
        for name in profile_mod.PROFILE_DOC_ORDER:
            doc = okf.load(self.lcp_home / "profile" / name)
            self.assertEqual(doc.type, "Profile")

    def test_seed_docs_state_precedence(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        for name in profile_mod.PROFILE_DOC_ORDER:
            text = (self.lcp_home / "profile" / name).read_text()
            self.assertIn(profile_mod.PRECEDENCE_LINE, text)
        self.assertIn(profile_mod.PRECEDENCE_LINE, (self.lcp_home / "profile" / "index.md").read_text())

    def test_rerun_does_not_touch_edited_content(self):
        """The whole point: editing a seed file and re-running must be safe."""
        profile_mod.ensure_scaffold(self.lcp_home)
        identity = self.lcp_home / "profile" / "identity.md"
        identity.write_text("---\ntype: Profile\n---\n\nReal content I wrote.\n")

        second = profile_mod.ensure_scaffold(self.lcp_home)

        self.assertEqual(identity.read_text(), "---\ntype: Profile\n---\n\nReal content I wrote.\n")
        self.assertNotIn(identity, second)

    def test_rerun_creates_nothing_new_when_complete(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        self.assertEqual(profile_mod.ensure_scaffold(self.lcp_home), [])

    def test_config_defaults(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        config = profile_mod.load_config(self.lcp_home)
        self.assertEqual(config["graphify"], "ask")
        self.assertEqual(config["project_root"], "~/code")


class TestAssemble(ProfileFixture):
    def test_missing_profile_raises_with_guidance(self):
        with self.assertRaises(profile_mod.ProfileError) as ctx:
            profile_mod.assemble(self.lcp_home)
        self.assertIn("path profile", str(ctx.exception))

    def test_assembled_output_contains_every_doc(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        text = profile_mod.assemble(self.lcp_home)
        for name in profile_mod.PROFILE_DOC_ORDER:
            self.assertIn(name.replace(".md", "").replace("-", " ").title().split()[0], text,
                          f"expected {name}'s heading to appear")

    def test_frontmatter_is_stripped_from_assembly(self):
        """The type/tags/timestamp fields are for Path's tooling, not for
        filling an agent's context window."""
        profile_mod.ensure_scaffold(self.lcp_home)
        text = profile_mod.assemble(self.lcp_home)
        self.assertNotIn("type: Profile", text)

    def test_precedence_line_appears_first(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        text = profile_mod.assemble(self.lcp_home)
        self.assertLess(text.index(profile_mod.PRECEDENCE_LINE), 200)

    def test_missing_individual_doc_is_skipped_not_fatal(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        (self.lcp_home / "profile" / "stack.md").unlink()
        text = profile_mod.assemble(self.lcp_home)  # must not raise
        self.assertIsInstance(text, str)


class TestAddEntry(ProfileFixture):
    def test_rejects_unknown_doc(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        with self.assertRaises(profile_mod.ProfileError) as ctx:
            profile_mod.add_entry(self.lcp_home, "nonsense", "some fact")
        message = str(ctx.exception)
        self.assertIn("nonsense", message)
        for name in profile_mod.PROFILE_DOC_NAMES:
            self.assertIn(name, message)

    def test_missing_profile_raises(self):
        with self.assertRaises(profile_mod.ProfileError):
            profile_mod.add_entry(self.lcp_home, "stack", "some fact")

    def test_appends_dated_entry_under_notes_heading(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        path = profile_mod.add_entry(self.lcp_home, "stack", "Prefers Python for scripting")
        text = path.read_text(encoding="utf-8")
        self.assertIn(profile_mod.NOTES_HEADER, text)
        self.assertIn("Prefers Python for scripting", text)

    def test_second_entry_does_not_duplicate_heading(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        profile_mod.add_entry(self.lcp_home, "stack", "First fact")
        path = profile_mod.add_entry(self.lcp_home, "stack", "Second fact")
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(profile_mod.NOTES_HEADER), 1)
        self.assertIn("First fact", text)
        self.assertIn("Second fact", text)

    def test_does_not_touch_existing_sections(self):
        """Only the timestamp field and the body's tail (the new Notes entry)
        may change — everything the seed template wrote stays put."""
        import okf

        profile_mod.ensure_scaffold(self.lcp_home)
        path = self.lcp_home / "profile" / "stack.md"
        before_body = okf.load(path).body

        profile_mod.add_entry(self.lcp_home, "stack", "A new fact")

        after = okf.load(path)
        self.assertTrue(after.body.startswith(before_body.rstrip("\n")))
        self.assertIn("A new fact", after.body)

    def test_refreshes_timestamp(self):
        import okf

        profile_mod.ensure_scaffold(self.lcp_home)
        path = self.lcp_home / "profile" / "stack.md"
        original_timestamp = okf.load(path).meta["timestamp"]

        import time

        time.sleep(1.1)
        profile_mod.add_entry(self.lcp_home, "stack", "A new fact")

        self.assertNotEqual(okf.load(path).meta["timestamp"], original_timestamp)

    def test_result_is_valid_okf(self):
        import okf

        profile_mod.ensure_scaffold(self.lcp_home)
        profile_mod.add_entry(self.lcp_home, "stack", "A new fact")
        doc = okf.load(self.lcp_home / "profile" / "stack.md")
        self.assertEqual(doc.type, "Profile")


class TestShims(ProfileFixture):
    def test_fresh_file_gets_just_the_block(self):
        target = self.tmp / "fresh.md"
        outcome = profile_mod._upsert_managed_block(target, self.lcp_home, apply=True)
        self.assertEqual(outcome, "added")
        text = target.read_text()
        self.assertIn(profile_mod.MARKER_START, text)
        self.assertIn("$LCP_HOME", text)

    def test_block_carries_the_write_standing_order(self):
        """F-52 — a pointer that only tells an agent to read the profile gives
        it no reason to ever write to it."""
        target = self.tmp / "fresh.md"
        profile_mod._upsert_managed_block(target, self.lcp_home, apply=True)
        text = target.read_text()
        self.assertIn("path profile add", text)

    def test_existing_content_is_preserved(self):
        """This is Kate's own ~/.claude/CLAUDE.md in miniature — must not lose
        the graphify block that was already there."""
        target = self.tmp / "existing.md"
        target.write_text("# graphify\n- trigger: /graphify\n")
        profile_mod._upsert_managed_block(target, self.lcp_home, apply=True)
        text = target.read_text()
        self.assertIn("# graphify", text)
        self.assertIn("trigger: /graphify", text)
        self.assertIn(profile_mod.MARKER_START, text)

    def test_rerun_is_idempotent(self):
        target = self.tmp / "f.md"
        profile_mod._upsert_managed_block(target, self.lcp_home, apply=True)
        first = target.read_text()
        outcome = profile_mod._upsert_managed_block(target, self.lcp_home, apply=True)
        self.assertEqual(outcome, "unchanged")
        self.assertEqual(target.read_text(), first)

    def test_rerun_updates_in_place_without_duplicating(self):
        target = self.tmp / "f.md"
        target.write_text(f"# Notes\n\n{profile_mod.MARKER_START}\nstale content\n{profile_mod.MARKER_END}\n")
        outcome = profile_mod._upsert_managed_block(target, self.lcp_home, apply=True)
        self.assertEqual(outcome, "updated")
        text = target.read_text()
        self.assertEqual(text.count(profile_mod.MARKER_START), 1)
        self.assertNotIn("stale content", text)
        self.assertIn("# Notes", text)

    def test_dry_run_writes_nothing(self):
        target = self.tmp / "f.md"
        profile_mod._upsert_managed_block(target, self.lcp_home, apply=False)
        self.assertFalse(target.exists())

    def test_install_shims_skips_undetected_tools(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        # No real ~/.claude or aider on a throwaway HOME; force both false.
        original = dict(profile_mod.SHIM_TARGETS)
        try:
            profile_mod.SHIM_TARGETS["claude"] = {
                "path": lambda: self.tmp / "claude.md", "detect": lambda: False
            }
            profile_mod.SHIM_TARGETS["aider"] = {
                "path": lambda: self.tmp / "aider.yml", "detect": lambda: False
            }
            results = profile_mod.install_shims(self.lcp_home, apply=True)
            self.assertEqual(results, {"claude": "not-detected", "aider": "not-detected"})
        finally:
            profile_mod.SHIM_TARGETS.clear()
            profile_mod.SHIM_TARGETS.update(original)

    def test_install_shims_writes_to_detected_tool(self):
        profile_mod.ensure_scaffold(self.lcp_home)
        target = self.tmp / "claude.md"
        original = dict(profile_mod.SHIM_TARGETS)
        try:
            profile_mod.SHIM_TARGETS["claude"] = {"path": lambda: target, "detect": lambda: True}
            profile_mod.SHIM_TARGETS["aider"] = {"path": lambda: target, "detect": lambda: False}
            results = profile_mod.install_shims(self.lcp_home, apply=True)
            self.assertEqual(results["claude"], "added")
            self.assertTrue(target.is_file())
        finally:
            profile_mod.SHIM_TARGETS.clear()
            profile_mod.SHIM_TARGETS.update(original)


if __name__ == "__main__":
    unittest.main()
