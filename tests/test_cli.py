from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT / "src"),
}


def run_gw(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = dict(ENV)
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "gw", *args],
        cwd=cwd,
        env=merged_env,
        text=True,
        capture_output=True,
    )


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


def init_repo(path: Path, default_branch: str = "main") -> None:
    git(path.parent, "init", "--initial-branch", default_branch, str(path))
    git(path, "config", "user.name", "gw tests")
    git(path, "config", "user.email", "gw@example.com")
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "initial")


def make_remote_clone(root: Path) -> tuple[Path, Path]:
    bare = root / "origin.git"
    work = root / "work"
    git(root, "init", "--bare", str(bare))
    init_repo(work)
    git(work, "remote", "add", "origin", str(bare))
    git(work, "push", "-u", "origin", "main")
    git(work, "remote", "set-head", "origin", "main")
    return bare, work


class GwCliTests(unittest.TestCase):
    def test_requires_base_worktree(self) -> None:
        with tempfile_dir() as tmp_path:
            repo = tmp_path / "repo"
            init_repo(repo)

            result = run_gw(["main"], repo)

            self.assertEqual(result.returncode, 1)
            self.assertIn("BASE_WORKTREE is not set", result.stderr)

    def test_requires_git_repo(self) -> None:
        with tempfile_dir() as tmp_path:
            base = tmp_path / "worktrees"
            base.mkdir()

            result = run_gw(["main"], tmp_path, env={"BASE_WORKTREE": str(base)})

            self.assertEqual(result.returncode, 1)
            self.assertIn("not inside a git repo", result.stderr)

    def test_checkout_existing_local_branch_reuses_worktree(self) -> None:
        with tempfile_dir() as tmp_path:
            repo = tmp_path / "repo"
            base = tmp_path / "worktrees"
            base.mkdir()
            init_repo(repo)
            git(repo, "branch", "feature/test")

            first = run_gw(["feature/test"], repo, env={"BASE_WORKTREE": str(base)})
            second = run_gw(["feature/test"], repo, env={"BASE_WORKTREE": str(base)})

            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(first.stdout.strip(), second.stdout.strip())
            self.assertTrue(Path(first.stdout.strip()).is_dir())

    def test_checkout_remote_branch_creates_local_worktree(self) -> None:
        with tempfile_dir() as tmp_path:
            _, repo = make_remote_clone(tmp_path)
            base = tmp_path / "worktrees"
            base.mkdir()

            git(repo, "checkout", "-b", "feature/remote")
            (repo / "remote.txt").write_text("remote\n", encoding="utf-8")
            git(repo, "add", "remote.txt")
            git(repo, "commit", "-m", "remote branch")
            git(repo, "push", "-u", "origin", "feature/remote")
            git(repo, "checkout", "main")
            git(repo, "branch", "-D", "feature/remote")

            result = run_gw(["feature/remote"], repo, env={"BASE_WORKTREE": str(base)})
            target = Path(result.stdout.strip())

            self.assertEqual(result.returncode, 0)
            self.assertTrue(target.is_dir())
            self.assertEqual(
                git(repo, "show-ref", "--verify", "--quiet", "refs/heads/feature/remote", check=False).returncode,
                0,
            )

    def test_checkout_commit_ref(self) -> None:
        with tempfile_dir() as tmp_path:
            repo = tmp_path / "repo"
            base = tmp_path / "worktrees"
            base.mkdir()
            init_repo(repo)
            commit = git(repo, "rev-parse", "HEAD").stdout.strip()

            result = run_gw([commit], repo, env={"BASE_WORKTREE": str(base)})

            self.assertEqual(result.returncode, 0)
            self.assertTrue(Path(result.stdout.strip()).is_dir())

    def test_create_branch(self) -> None:
        with tempfile_dir() as tmp_path:
            repo = tmp_path / "repo"
            base = tmp_path / "worktrees"
            base.mkdir()
            init_repo(repo)

            result = run_gw(["-b", "feature/new"], repo, env={"BASE_WORKTREE": str(base)})

            self.assertEqual(result.returncode, 0)
            self.assertTrue(Path(result.stdout.strip()).is_dir())
            self.assertEqual(
                git(repo, "show-ref", "--verify", "--quiet", "refs/heads/feature/new", check=False).returncode,
                0,
            )

    def test_print_shell_integration_does_not_require_repo(self) -> None:
        with tempfile_dir() as tmp_path:
            result = run_gw(["--print-shell-integration", "zsh"], tmp_path)

            self.assertEqual(result.returncode, 0)
            self.assertIn("compdef _gw_complete gw", result.stdout)
            self.assertEqual(result.stderr, "")

    def test_base_branch_mode_prunes_gone_branches(self) -> None:
        with tempfile_dir() as tmp_path:
            _, repo = make_remote_clone(tmp_path)
            base = tmp_path / "worktrees"
            base.mkdir()

            git(repo, "checkout", "-b", "stale")
            git(repo, "push", "-u", "origin", "stale")
            git(repo, "checkout", "main")
            git(repo, "push", "origin", "--delete", "stale")

            result = run_gw(["-base", "main", "-b", "feature/from-main"], repo, env={"BASE_WORKTREE": str(base)})

            self.assertEqual(result.returncode, 0)
            self.assertIn("cleaning up gone branches", result.stderr)
            self.assertNotEqual(
                git(repo, "show-ref", "--verify", "--quiet", "refs/heads/stale", check=False).returncode,
                0,
            )

    def test_safe_delete_fails_for_unmerged_branch(self) -> None:
        with tempfile_dir() as tmp_path:
            repo = tmp_path / "repo"
            base = tmp_path / "worktrees"
            base.mkdir()
            init_repo(repo)

            create_result = run_gw(["-b", "feature/unmerged"], repo, env={"BASE_WORKTREE": str(base)})
            branch_repo = Path(create_result.stdout.strip())
            (branch_repo / "change.txt").write_text("change\n", encoding="utf-8")
            git(branch_repo, "add", "change.txt")
            git(branch_repo, "commit", "-m", "branch change")
            git(repo, "checkout", "main")

            result = run_gw(["-d", "feature/unmerged"], repo, env={"BASE_WORKTREE": str(base)})

            self.assertEqual(result.returncode, 1)
            self.assertTrue(
                "not fully merged" in result.stderr
                or "is not an ancestor" in result.stderr
                or "error:" in result.stderr
            )
            self.assertTrue(branch_repo.exists())

    def test_force_delete_succeeds(self) -> None:
        with tempfile_dir() as tmp_path:
            repo = tmp_path / "repo"
            base = tmp_path / "worktrees"
            base.mkdir()
            init_repo(repo)

            create_result = run_gw(["-b", "feature/force"], repo, env={"BASE_WORKTREE": str(base)})
            branch_repo = Path(create_result.stdout.strip())
            (branch_repo / "change.txt").write_text("change\n", encoding="utf-8")
            git(branch_repo, "add", "change.txt")
            git(branch_repo, "commit", "-m", "branch change")
            git(repo, "checkout", "main")

            result = run_gw(["-D", "feature/force"], repo, env={"BASE_WORKTREE": str(base)})

            self.assertEqual(result.returncode, 0)
            self.assertFalse(branch_repo.exists())
            self.assertNotEqual(
                git(repo, "show-ref", "--verify", "--quiet", "refs/heads/feature/force", check=False).returncode,
                0,
            )

    def test_default_branch_reuses_main_worktree(self) -> None:
        with tempfile_dir() as tmp_path:
            _, repo = make_remote_clone(tmp_path)
            base = tmp_path / "worktrees"
            base.mkdir()

            result = run_gw(["main"], repo, env={"BASE_WORKTREE": str(base)})

            self.assertEqual(result.returncode, 0)
            self.assertEqual(Path(result.stdout.strip()), repo.resolve())

    def test_manual_includes_are_copied(self) -> None:
        with tempfile_dir() as tmp_path:
            repo = tmp_path / "repo"
            base = tmp_path / "worktrees"
            base.mkdir()
            init_repo(repo)

            (repo / ".gitignore").write_text(".env\nnode_modules/\n", encoding="utf-8")
            (repo / ".env").write_text("SECRET=1\n", encoding="utf-8")
            (repo / "node_modules").mkdir()
            (repo / "node_modules" / "ignored.txt").write_text("ignored\n", encoding="utf-8")
            (repo / ".gw" / "includes").mkdir(parents=True)
            (repo / ".gw" / "includes" / "manual_includes").write_text(".env\n", encoding="utf-8")
            (repo / ".gw" / "config").write_text("data\n", encoding="utf-8")
            git(repo, "add", ".gitignore")
            git(repo, "commit", "-m", "add gw config")

            result = run_gw(["-b", "feature/includes"], repo, env={"BASE_WORKTREE": str(base)})
            target = Path(result.stdout.strip())

            self.assertEqual(result.returncode, 0)
            self.assertEqual((target / ".env").read_text(encoding="utf-8"), "SECRET=1\n")
            self.assertEqual((target / ".gw" / "config").read_text(encoding="utf-8"), "data\n")
            self.assertFalse((target / "node_modules" / "ignored.txt").exists())

    @unittest.skipIf(sys.platform == "darwin", "non-macOS rejection only applies off macOS")
    def test_new_mode_is_rejected_off_macos(self) -> None:
        with tempfile_dir() as tmp_path:
            repo = tmp_path / "repo"
            base = tmp_path / "worktrees"
            base.mkdir()
            init_repo(repo)

            result = run_gw(["-new", "tab", "main"], repo, env={"BASE_WORKTREE": str(base)})

            self.assertEqual(result.returncode, 1)
            self.assertIn("-new requires macOS", result.stderr)

    def test_new_mode_invokes_osascript_when_supported(self) -> None:
        import gw.cli as cli

        repo = Path("/tmp/fake-repo")
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], capture_output: bool = False, text: bool = False, check: bool = False):
            calls.append(cmd)

            class Result:
                returncode = 0
                stdout = "iTerm2"
                stderr = ""

            return Result()

        with mock.patch.object(cli, "get_repo_info", return_value=("repo", "/tmp/worktrees/repo", str(repo))), \
            mock.patch.object(cli, "get_default_branch", return_value="main"), \
            mock.patch.object(cli, "find_worktree_for_local_branch", return_value=None), \
            mock.patch.object(cli, "copy_manual_includes"), \
            mock.patch.object(cli, "git"), \
            mock.patch.object(cli.shutil, "which", return_value="/usr/bin/osascript"), \
            mock.patch.object(cli.sys, "platform", "darwin"), \
            mock.patch.object(cli.subprocess, "run", side_effect=fake_run):
            exit_code = cli.run(["-new", "tab", "main"], prog_name="gw")

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls[0][0], "osascript")
        self.assertEqual(calls[1][0], "osascript")


class tempfile_dir:
    def __enter__(self) -> Path:
        import tempfile

        self._tmpdir = tempfile.TemporaryDirectory()
        return Path(self._tmpdir.name)

    def __exit__(self, exc_type, exc, tb) -> None:
        self._tmpdir.cleanup()


if __name__ == "__main__":
    unittest.main()
