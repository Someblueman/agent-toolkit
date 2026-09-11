"""Real Git work intervals, including dirty starts and intermediate commits."""

import subprocess
import tempfile
from pathlib import Path

from quality_lib.config import SetupError
from quality_lib.review_scope import capture, diff_command, git
from support import Repository


class ReviewScope(Repository):
    def setUp(self):
        super().setUp()
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Probe")
        git(self.root, "config", "user.email", "probe@example.invalid")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.scope = Path(temporary.name)

    def commit(self):
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "checkpoint")

    def test_scope_spans_commits_dirty_files_modes_and_deletions(self):
        (self.root / "removed").write_text("remove me\n")
        self.commit()
        self.source.write_text("preexisting = 2\n")
        git(self.root, "add", ".")
        (self.root / "user scratch").write_text("leave alone\n")
        index = (self.root / ".git/index").read_bytes()
        objects = sorted((self.root / ".git/objects").rglob("*"))
        before = capture(self.root, self.scope)
        self.assertEqual((self.root / ".git/index").read_bytes(), index)
        self.assertEqual(sorted((self.root / ".git/objects").rglob("*")), objects)
        self.source.write_text("preexisting = 2\nnew = 3\n")
        self.commit()
        self.source.chmod(0o755)
        (self.root / "removed").unlink()
        self.commit()
        (self.root / "uncommitted ' file").write_text("new content\n")
        index = (self.root / ".git/index").read_bytes()
        after = capture(self.root, self.scope)
        output = subprocess.check_output(
            diff_command(self.scope, before, after), text=True
        )
        self.assertIn("+new = 3", output)
        self.assertIn("new mode 100755", output)
        self.assertIn("deleted file mode", output)
        self.assertIn("uncommitted ' file", output)
        self.assertNotIn("user scratch", output)
        self.assertNotIn("+preexisting", output)
        self.assertEqual((self.root / ".git/index").read_bytes(), index)

    def test_unborn_repository_and_unchanged_reads(self):
        before = capture(self.root, self.scope)
        self.assertEqual(capture(self.root, self.scope), before)
        self.assertFalse((self.root / ".git/index").exists())
        self.source.write_text("value = 2\n")
        self.assertNotEqual(capture(self.root, self.scope), before)

    def test_linked_checkout_uses_its_own_head(self):
        self.commit()
        target = self.scope / "linked checkout"
        git(self.root, "worktree", "add", "-qb", "probe", str(target))
        source = target / "src/example.py"
        source.write_text("linked = 9\n")
        git(target, "add", ".")
        git(target, "commit", "-qm", "linked change")
        tree = capture(target, self.scope / "linked scope")
        self.assertEqual(tree, git(target, "rev-parse", "HEAD^{tree}"))

    def test_merge_conflict_is_explicitly_unavailable(self):
        self.commit()
        git(self.root, "checkout", "-qb", "side")
        self.source.write_text("side = 2\n")
        self.commit()
        git(self.root, "checkout", "-q", "-")
        self.source.write_text("main = 3\n")
        self.commit()
        subprocess.run(
            ["git", "merge", "side"], cwd=self.root, capture_output=True, check=False
        )
        with self.assertRaisesRegex(SetupError, "merge conflicts"):
            capture(self.root, self.scope)

    def test_sparse_checkout_and_changed_submodules_are_explicitly_unavailable(self):
        self.commit()
        git(self.root, "config", "core.sparseCheckout", "true")
        with self.assertRaisesRegex(SetupError, "sparse checkout"):
            capture(self.root, self.scope)
        git(self.root, "config", "core.sparseCheckout", "false")
        child = self.scope / "child"
        child.mkdir()
        git(child, "init", "-q")
        git(child, "config", "user.name", "Probe")
        git(child, "config", "user.email", "probe@example.invalid")
        (child / "value").write_text("original\n")
        git(child, "add", ".")
        git(child, "commit", "-qm", "child")
        git(
            self.root,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(child),
            "module",
        )
        self.commit()
        capture(self.root, self.scope)
        (self.root / "module/value").write_text("changed\n")
        with self.assertRaisesRegex(SetupError, "changed submodules"):
            capture(self.root, self.scope)
