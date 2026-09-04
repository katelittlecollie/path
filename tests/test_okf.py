"""Tests for scripts/okf.py.

The contract under test is round-trip fidelity: reading a document and writing
it back unchanged must not alter a single byte. Path rewrites frontmatter every
time it appends a log entry, so any reformatting the serializer does lands in
the diff of a file nobody edited.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import okf  # noqa: E402


TASK = """---
type: Task
title: Sync with Path revisions
tags: [path, maintenance]
timestamp: 2026-07-16T10:00:00Z
path:
  id: T-023
  status: pending
  effort: 3
  created: 2026-07-16
  completed: null
  requires: [T-019]
  completed_by: []
  drift_log:
  - date: 2026-07-16
    kind: correction
    effort_to_correct: 2
---

## Objective

Body prose.
"""


class TestRoundTrip(unittest.TestCase):
    def test_byte_identical(self):
        self.assertEqual(okf.dumps(okf.loads(TASK, "t.md")), TASK)

    def test_idempotent(self):
        once = okf.dumps(okf.loads(TASK, "t.md"))
        twice = okf.dumps(okf.loads(once, "t.md"))
        self.assertEqual(once, twice)

    def test_preserves_unknown_keys(self):
        """OKF requires consumers to preserve keys they do not understand."""
        src = TASK.replace("type: Task", "type: Task\nfuture_okf_field: kept")
        out = okf.dumps(okf.loads(src, "t.md"))
        self.assertIn("future_okf_field: kept", out)

    def test_preserves_key_order(self):
        doc = okf.loads(TASK, "t.md")
        self.assertEqual(list(doc.meta)[:3], ["type", "title", "tags"])

    def test_timestamp_keeps_iso_form(self):
        """PyYAML would parse this to a datetime and re-emit `2026-07-16 10:00:00+00:00`."""
        out = okf.dumps(okf.loads(TASK, "t.md"))
        self.assertIn("timestamp: 2026-07-16T10:00:00Z", out)

    def test_dates_are_not_quoted(self):
        out = okf.dumps(okf.loads(TASK, "t.md"))
        self.assertNotIn("'2026-07-16'", out)

    def test_scalar_lists_inline_mapping_lists_block(self):
        out = okf.dumps(okf.loads(TASK, "t.md"))
        self.assertIn("tags: [path, maintenance]", out)
        self.assertIn("drift_log:\n  - date:", out)

    def test_blank_line_after_frontmatter_survives(self):
        out = okf.dumps(okf.loads(TASK, "t.md"))
        self.assertIn("---\n\n## Objective", out)

    def test_body_containing_triple_dash(self):
        src = TASK + "\nA line with --- in it.\n"
        doc = okf.loads(src, "t.md")
        self.assertIn("--- in it", doc.body)
        self.assertEqual(okf.dumps(doc), src)

    def test_crlf_input_parses(self):
        doc = okf.loads(TASK.replace("\n", "\r\n"), "t.md")
        self.assertEqual(doc.meta["type"], "Task")

    def test_body_that_is_not_valid_yaml(self):
        """The body is never handed to a YAML parser, so it cannot break parsing.

        This is the trap that catches yq: `---` is a YAML document separator, so
        a YAML parser reads an OKF file as frontmatter plus a second document
        made of Markdown, and chokes on a table or a colon. Splitting on the
        frontmatter delimiter with a regex, and parsing only what is between the
        markers, sidesteps it. See blueprints/06-okf-mapping.md.
        """
        src = (
            "---\ntype: Task\npath:\n  id: T-003\n---\n\n"
            "## Objective\n\nShip the thing: properly.\n\n"
            "---\n\n"                                  # a Markdown horizontal rule
            "| Item | In scope? |\n|------|----|\n| Auth | yes |\n\n"
            '```bash\necho "a fence: with a colon"\n```\n'
        )
        doc = okf.loads(src, "t.md")
        self.assertEqual(doc.meta["path"]["id"], "T-003")
        self.assertIn("| Auth | yes |", doc.body)
        self.assertEqual(okf.dumps(doc), src)


class TestErrors(unittest.TestCase):
    def test_missing_frontmatter_raises(self):
        with self.assertRaises(okf.OKFError):
            okf.loads("# Just a heading\n", "t.md")

    def test_unparseable_yaml_raises(self):
        with self.assertRaises(okf.OKFError):
            okf.loads("---\n: : :\n---\nbody\n", "t.md")

    def test_non_mapping_frontmatter_raises(self):
        with self.assertRaises(okf.OKFError):
            okf.loads("---\n- a list\n---\nbody\n", "t.md")

    def test_path_block_must_be_mapping(self):
        doc = okf.loads("---\ntype: Task\npath: not-a-mapping\n---\n", "t.md")
        with self.assertRaises(okf.OKFError):
            _ = doc.path_meta


class TestReserved(unittest.TestCase):
    def test_reserved_names(self):
        self.assertTrue(okf.is_reserved(Path("a/index.md")))
        self.assertTrue(okf.is_reserved(Path("a/log.md")))
        self.assertFalse(okf.is_reserved(Path("a/decisions-log.md")))
        self.assertFalse(okf.is_reserved(Path("a/T-001-x.md")))

    def test_loading_reserved_file_raises(self):
        with self.assertRaises(okf.OKFError):
            okf.load(Path("index.md"))


class TestDoc(unittest.TestCase):
    def test_path_meta_created_on_access(self):
        doc = okf.loads("---\ntype: Task\n---\n", "t.md")
        doc.path_meta["id"] = "T-001"
        self.assertIn("path:\n  id: T-001", okf.dumps(doc))

    def test_empty_frontmatter_is_empty_mapping(self):
        doc = okf.loads("---\n\n---\nbody\n", "t.md")
        self.assertEqual(doc.meta, {})
        self.assertIsNone(doc.type)


class ProjectRootFixture(unittest.TestCase):
    """A real filesystem tree, not fixtures inside the real Path repo — these
    tests are about the resolution logic itself, which has two genuinely
    different roles hiding behind one function each and needs its own
    coverage rather than only ever being exercised end-to-end via the CLI."""

    def setUp(self):
        # Resolved once, here: on macOS, tempfile.mkdtemp() returns a path under
        # /var/folders/..., a symlink to /private/var/folders/... — the code
        # under test calls .resolve() internally, so an unresolved self.tmp
        # would compare unequal to its own correct return value.
        self.tmp = Path(tempfile.mkdtemp()).resolve()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def make_repo(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / ".git").mkdir()


class TestFindProjectRoot(ProjectRootFixture):
    def test_finds_the_nested_dotfile_layout(self):
        project = self.tmp / "myproject"
        self.make_repo(project)
        (project / ".path" / "blueprints").mkdir(parents=True)
        found = okf.find_project_root(project)
        self.assertEqual(found, project / ".path")

    def test_a_bare_path_directory_is_not_recognized(self):
        """The old, pre-dotfile convention. A project still nested at a plain
        `path/` needs an explicit rename — this is a clean cutover, not a
        dual-recognized transition period."""
        project = self.tmp / "myproject"
        self.make_repo(project)
        (project / "path" / "blueprints").mkdir(parents=True)
        self.assertIsNone(okf.find_project_root(project))

    def test_finds_the_self_hosted_layout(self):
        """requirements/ and blueprints/ directly at a repo's own root — how
        the Path product repository itself is laid out."""
        repo = self.tmp / "path"
        self.make_repo(repo)
        (repo / "requirements").mkdir()
        (repo / "blueprints").mkdir()
        self.assertEqual(okf.find_project_root(repo), repo)

    def test_finds_the_root_from_a_subdirectory(self):
        project = self.tmp / "myproject"
        self.make_repo(project)
        (project / ".path" / "blueprints").mkdir(parents=True)
        deep = project / "apps" / "mail" / "lib"
        deep.mkdir(parents=True)
        self.assertEqual(okf.find_project_root(deep), project / ".path")

    def test_returns_none_outside_any_project(self):
        bare = self.tmp / "nothing_here"
        self.make_repo(bare)
        self.assertIsNone(okf.find_project_root(bare))

    def test_stops_at_the_repo_boundary(self):
        """Must not wander up past a git repo's own root looking for a parent
        project — that would find something that isn't really this
        repository's documentation."""
        outer_project = self.tmp / "outer"
        (outer_project / ".path" / "blueprints").mkdir(parents=True)
        inner_repo = outer_project / "vendored-thing"
        self.make_repo(inner_repo)
        self.assertIsNone(okf.find_project_root(inner_repo))


class TestProjectDir(ProjectRootFixture):
    def test_self_hosted_root_is_its_own_project_dir(self):
        repo = self.tmp / "path"
        self.make_repo(repo)
        self.assertEqual(okf.project_dir(repo), repo)

    def test_nested_dotfile_root_returns_its_parent(self):
        project = self.tmp / "myproject"
        self.make_repo(project)
        nested = project / ".path"
        nested.mkdir()
        self.assertEqual(okf.project_dir(nested), project)

    def test_a_bare_path_directory_is_treated_as_self_hosted(self):
        """`.path` is the only nested signal now — unambiguous, since
        `init_project`/`migrate` never create a bare (non-dotted) `path`
        directory. A repo that happens to be named plain `path` (the Path
        product repository itself, on this machine) is therefore always its
        own project_dir, with no `.git` check required to disambiguate it."""
        outer = self.tmp / "outer"
        outer.mkdir()
        bare_path = outer / "path"
        bare_path.mkdir()
        self.assertEqual(okf.project_dir(bare_path), bare_path)

    def test_a_nested_project_dir_is_not_named_path_at_all(self):
        """The common case going forward: a consumer project's root is
        whatever the project is called, and its docs live in a `.path/`
        beneath it — `.path` itself is never what project_dir returns."""
        project = self.tmp / "lcm"
        self.make_repo(project)
        self.assertEqual(okf.project_dir(project), project)


if __name__ == "__main__":
    unittest.main()
