"""Real Git worktrees, owned changes, and caller integration acceptance."""

import json
import subprocess
import unittest

from workflow_fixture import WorkflowCase, member


class WorkflowOwnership(WorkflowCase):
    def git(self, directory, *args):
        return subprocess.run(
            ["git", "-C", str(directory), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git(self.repo, "init", "-b", "main")
        self.git(self.repo, "config", "user.email", "fixture@example.invalid")
        self.git(self.repo, "config", "user.name", "Fixture")
        for file in ("left.py", "right.py"):
            (self.repo / file).write_text("VALUE = 0\n")
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-m", "base")
        self.base = self.git(self.repo, "rev-parse", "HEAD")
        self.assignments = self.root / "assignments.json"
        self.items = []
        for name in ("left", "right"):
            worktree = self.root / name
            self.git(self.repo, "worktree", "add", "-b", name, str(worktree), self.base)
            self.items.append(
                {
                    "id": name,
                    "member": "author",
                    "task": "Set VALUE to 1",
                    "working_directory": str(worktree),
                    "base": self.base,
                    "owned_paths": [name + ".py"],
                    "acceptance": [
                        f'python3 -B -c "import {name}; assert {name}.VALUE == 1"'
                    ],
                    "interfaces": "Retain VALUE integer constant.",
                    "depends_on": [],
                }
            )
        self.configure(
            [member("author"), member("unused", "claude", "hang")], "implement"
        )

    def run_assignments(self, items=None):
        self.assignments.write_text(
            json.dumps(
                {"version": 1, "assignments": self.items if items is None else items}
            )
        )
        return self.run_workflow(
            "implement", extra=["--assignments", str(self.assignments)]
        )

    def test_owned_commits_integrate_and_combined_check_is_real(self):
        result = self.run_assignments()
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = self.packet()
        self.assertEqual(packet["requested_workers"], 2)
        self.assertEqual(
            [w["member_id"] for w in packet["workers"]], ["author", "author"]
        )
        for worker in packet["workers"]:
            self.assertTrue(worker["ownership"]["conforming"])
            self.git(self.repo, "cherry-pick", worker["ownership"]["head"])
        checked = subprocess.run(
            [
                "python3",
                "-B",
                "-c",
                "import left,right; assert left.VALUE + right.VALUE == 2",
            ],
            cwd=self.repo,
            check=False,
        )
        self.assertEqual(checked.returncode, 0)
        # A stronger integration constraint can still fail despite green individual checks.
        checked = subprocess.run(
            [
                "python3",
                "-B",
                "-c",
                "import left,right; assert left.VALUE != right.VALUE",
            ],
            cwd=self.repo,
            check=False,
            capture_output=True,
        )
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("integration_and_verification_pending", packet["scope"])

    def test_reject_overlap_duplicate_checkout_unknown_member_prerequisite_dirty(self):
        for replacement in [
            {"owned_paths": ["left.py"]},
            {"working_directory": self.items[0]["working_directory"]},
            {"member": "absent"},
            {"depends_on": ["not-a-commit"]},
            {"owned_paths": ["../outside"]},
        ]:
            with self.subTest(replacement=replacement):
                items = [self.items[0], {**self.items[1], **replacement}]
                result = self.run_assignments(items)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.events.exists())
        (self.root / "left" / "dirty").write_text("x")
        self.assertEqual(self.run_assignments().returncode, 2)

    def test_out_of_scope_untracked_edit_is_retained_and_rejected(self):
        self.configure([member("author", model="outside")], "implement")
        result = self.run_assignments()
        self.assertEqual(result.returncode, 1, result.stderr)
        for worker in self.packet()["workers"]:
            self.assertEqual(worker["status"], "nonconforming")
            self.assertIn("outside.txt", worker["ownership"]["violations"])
        self.assertTrue((self.root / "left" / "outside.txt").exists())

    def test_readonly_harness_and_symlink_are_rejected(self):
        self.configure([member("author", "agy")], "implement")
        self.assertEqual(self.run_assignments().returncode, 2)
        self.configure([member("author")], "implement")
        (self.root / "left" / "link").symlink_to(self.root / "right" / "right.py")
        self.git(self.root / "left", "add", "link")
        self.git(self.root / "left", "commit", "-m", "symlink")
        item = {
            **self.items[0],
            "base": self.git(self.root / "left", "rev-parse", "HEAD"),
        }
        self.assertEqual(self.run_assignments([item]).returncode, 2)


if __name__ == "__main__":
    unittest.main()
