"""CLI implementation for gw."""

from __future__ import annotations

import argparse
import enum
import fnmatch
import os
from pathlib import Path
import shutil
import subprocess
import sys


class NewMode(enum.Enum):
    TAB = "tab"
    WINDOW = "window"
    SPLIT_H = "split-h"
    SPLIT_V = "split-v"


class GwError(RuntimeError):
    """Raised for user-facing gw failures."""


ITERM_SCRIPTS: dict[NewMode, str] = {
    NewMode.TAB: """
tell application "iTerm2"
    tell current window
        create tab with default profile
        tell current session
            write text "cd {path}"
        end tell
    end tell
end tell
""",
    NewMode.WINDOW: """
tell application "iTerm2"
    set newWindow to (create window with default profile)
    tell current session of newWindow
        write text "cd {path}"
    end tell
end tell
""",
    NewMode.SPLIT_H: """
tell application "iTerm2"
    tell current session of current window
        set newSession to (split horizontally with default profile)
        tell newSession
            write text "cd {path}"
        end tell
    end tell
end tell
""",
    NewMode.SPLIT_V: """
tell application "iTerm2"
    tell current session of current window
        set newSession to (split vertically with default profile)
        tell newSession
            write text "cd {path}"
        end tell
    end tell
end tell
""",
}

ZSH_INTEGRATION = """gw() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    command gw --help
    return $?
  fi

  local path rc
  path="$(command gw "$@")"
  rc=$?

  if (( rc != 0 )); then
    return "$rc"
  fi

  if [[ -n "$path" && -d "$path" ]]; then
    cd "$path" || return 1
  fi
}

_gw_complete() {
  if [[ "$PREFIX" == -* ]]; then
    local -a flags=(
      '--print-shell-integration:print shell helper script'
      '-new:open worktree in a new iTerm2 tab/window/split pane'
      '-b:create new branch and worktree'
      '-base:update base branch before creating a new branch'
      '-d:remove worktree and delete branch'
      '-D:force-remove worktree and delete branch'
    )
    _describe 'flag' flags
    return
  fi

  local -a local_branches remote_branches branches
  local remote_branch

  local_branches=( ${(f)"$(git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null)"} )
  remote_branches=( ${(f)"$(git for-each-ref --format='%(refname:lstrip=3)' refs/remotes/ 2>/dev/null | grep -v '^HEAD$' | sort -u)"} )

  branches=( $local_branches )
  for remote_branch in $remote_branches; do
    if (( ! ${local_branches[(Ie)$remote_branch]} )); then
      branches+=( "$remote_branch" )
    fi
  done

  if [[ ${#words} -eq 2 ]]; then
    branches=( "co" $branches )
  fi

  _describe 'branch' branches
}

compdef _gw_complete gw
compdef _gw_complete git-gw
_git_gw() { _gw_complete "$@"; }
"""

BASH_INTEGRATION = """gw() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    command gw --help
    return $?
  fi

  local path rc
  path="$(command gw "$@")"
  rc=$?

  if [[ $rc -ne 0 ]]; then
    return "$rc"
  fi

  if [[ -n "$path" && -d "$path" ]]; then
    cd "$path" || return 1
  fi
}

_gw_complete() {
  local cur
  cur="${COMP_WORDS[COMP_CWORD]}"

  if [[ "$cur" == -* ]]; then
    COMPREPLY=( $(compgen -W "--print-shell-integration -new -b -base -d -D" -- "$cur") )
    return
  fi

  local local_branches remote_branches
  local_branches="$(git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null)"
  remote_branches="$(git for-each-ref --format='%(refname:lstrip=3)' refs/remotes/ 2>/dev/null | grep -v '^HEAD$' | sort -u)"
  COMPREPLY=( $(compgen -W "co ${local_branches} ${remote_branches}" -- "$cur") )
}

complete -F _gw_complete gw
complete -F _gw_complete git-gw
"""


def err(message: str) -> None:
    print(message, file=sys.stderr)


def git(*args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=capture,
        text=True,
        check=check,
    )


def git_output(*args: str) -> str:
    result = git(*args, capture=True, check=True)
    return result.stdout.strip()


def git_check(*args: str) -> bool:
    result = git(*args, capture=True, check=False)
    return result.returncode == 0


def sanitize(name: str) -> str:
    return name.replace("/", "__")


def find_worktree_for_local_branch(branch: str) -> str | None:
    target_ref = f"refs/heads/{branch}"
    result = git("worktree", "list", "--porcelain", capture=True, check=True)
    current_worktree = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_worktree = line[len("worktree ") :]
        elif line.startswith("branch ") and line[len("branch ") :] == target_ref:
            return current_worktree
    return None


def get_default_branch() -> str | None:
    result = git("symbolic-ref", "refs/remotes/origin/HEAD", capture=True, check=False)
    if result.returncode == 0:
        return result.stdout.strip().removeprefix("refs/remotes/origin/")
    return None


def target_dir_for(name: str, repo_base: str) -> str:
    return str(Path(repo_base, sanitize(name)).resolve())


def copy_manual_includes(main_root: str, target: str) -> None:
    gw_src = os.path.join(main_root, ".gw")
    if os.path.isdir(gw_src):
        gw_dst = os.path.join(target, ".gw")
        if os.path.exists(gw_dst):
            shutil.rmtree(gw_dst)
        shutil.copytree(gw_src, gw_dst)
        err("gw: copied .gw/")

    includes_file = os.path.join(main_root, ".gw", "includes", "manual_includes")
    if not os.path.isfile(includes_file):
        return

    patterns: list[str] = []
    with open(includes_file, encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if line:
                patterns.append(line)

    if not patterns:
        return

    copied = 0
    for dirpath, dirnames, filenames in os.walk(main_root):
        rel_dir = os.path.relpath(dirpath, main_root)
        if rel_dir == ".":
            rel_dir = ""

        if ".git" in dirnames:
            dirnames.remove(".git")

        to_remove: list[str] = []
        for dirname in dirnames:
            dir_rel = os.path.join(rel_dir, dirname) if rel_dir else dirname
            if git_check("-C", main_root, "check-ignore", "-q", dir_rel):
                to_remove.append(dirname)
        for dirname in to_remove:
            dirnames.remove(dirname)

        for filename in filenames:
            file_rel = os.path.join(rel_dir, filename) if rel_dir else filename
            matched = False
            for pattern in patterns:
                if "/" in pattern:
                    matched = fnmatch.fnmatch(file_rel, pattern)
                else:
                    matched = fnmatch.fnmatch(filename, pattern)
                if matched:
                    break

            if matched:
                destination = os.path.join(target, file_rel)
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                shutil.copy2(os.path.join(main_root, file_rel), destination)
                copied += 1

    if copied > 0:
        err(f"gw: copied {copied} file(s) from .gw/includes/manual_includes")


def open_iterm(path: str, mode: NewMode) -> None:
    script = ITERM_SCRIPTS[mode].format(path=path)
    subprocess.run(["osascript", "-e", script], check=True)


def emit_path(path: str, new_mode: NewMode | None) -> str:
    canonical_path = str(Path(path).resolve())
    if new_mode:
        open_iterm(canonical_path, new_mode)
        return ""
    return canonical_path


def finish_new_worktree(target_path: str, main_worktree_root: str | None, new_mode: NewMode | None) -> str:
    if main_worktree_root:
        copy_manual_includes(main_worktree_root, target_path)
    return emit_path(target_path, new_mode)


def get_repo_info() -> tuple[str, str, str | None]:
    base_worktree = os.environ.get("BASE_WORKTREE", "")
    if not base_worktree:
        raise GwError(
            "gw: BASE_WORKTREE is not set.\n\n"
            "Create a base directory for worktrees and export it in your shell config:\n\n"
            '  mkdir -p "$HOME/worktrees"\n'
            '  export BASE_WORKTREE="$HOME/worktrees"\n'
        )

    if not os.path.isdir(base_worktree):
        raise GwError(
            f"gw: BASE_WORKTREE '{base_worktree}' does not exist. Create it first:\n"
            f'  mkdir -p "{base_worktree}"'
        )

    if not git_check("rev-parse", "--is-inside-work-tree"):
        raise GwError("gw: not inside a git repo.")

    common_dir = git_output("rev-parse", "--path-format=absolute", "--git-common-dir")
    if os.path.basename(common_dir) == ".git":
        repo_dir = os.path.dirname(common_dir)
        repo_name = os.path.basename(repo_dir)
        main_worktree_root = repo_dir
    else:
        repo_name = os.path.basename(common_dir)
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        main_worktree_root = None

    repo_base = os.path.join(base_worktree, repo_name)
    os.makedirs(repo_base, exist_ok=True)
    return repo_name, repo_base, main_worktree_root


def update_base_branch(base: str, main_worktree_root: str | None) -> None:
    worktree_path = find_worktree_for_local_branch(base)
    if not worktree_path:
        remote_check = git("branch", "-r", "--list", f"*/{base}", capture=True, check=True)
        if not git_check("show-ref", "--verify", "--quiet", f"refs/heads/{base}") and not remote_check.stdout.strip():
            raise GwError(f"gw: base branch '{base}' not found")
        if main_worktree_root:
            git("-C", main_worktree_root, "checkout", base, capture=True)
            worktree_path = main_worktree_root
        else:
            raise GwError(f"gw: base branch '{base}' has no worktree and no main worktree is available")

    err("gw: cleaning up gone branches...")
    git("fetch", "--prune", capture=True)
    result = git("branch", "-vv", capture=True, check=True)
    for line in result.stdout.splitlines():
        if ": gone]" not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("* "):
            stripped = stripped[2:]
        branch_name = stripped.split()[0]
        git("branch", "-D", branch_name, capture=True, check=False)
        err(f"gw: deleted gone branch '{branch_name}'")


def do_delete(branch: str, force: bool) -> None:
    worktree_path = find_worktree_for_local_branch(branch)
    branch_exists = git_check("show-ref", "--verify", "--quiet", f"refs/heads/{branch}")

    if not worktree_path and not branch_exists:
        raise GwError(f"gw: branch '{branch}' not found")

    if not force and branch_exists:
        result = git("branch", "-d", branch, capture=True, check=False)
        if result.returncode != 0:
            stderr = result.stderr or ""
            if "used by worktree" in stderr:
                merged = git("merge-base", "--is-ancestor", branch, "HEAD", check=False)
                if merged.returncode != 0:
                    raise GwError(f"gw: branch '{branch}' is not fully merged (use -D to force)")
            else:
                raise GwError(stderr.rstrip())
        else:
            branch_exists = False

    if worktree_path:
        if force:
            git("worktree", "remove", "--force", worktree_path)
        else:
            git("worktree", "remove", worktree_path)
        err(f"gw: removed worktree '{worktree_path}'")

    if branch_exists:
        if force:
            git("branch", "-D", branch)
        else:
            git("branch", "-d", branch)


def do_create_branch(
    new_branch: str,
    base: str | None,
    repo_base: str,
    main_worktree_root: str | None,
    new_mode: NewMode | None,
) -> str:
    existing = find_worktree_for_local_branch(new_branch)
    if existing:
        return emit_path(existing, new_mode)

    if git_check("show-ref", "--verify", "--quiet", f"refs/heads/{new_branch}"):
        raise GwError(f"gw: branch '{new_branch}' already exists (use gw '{new_branch}')")

    target_path = target_dir_for(new_branch, repo_base)
    if base:
        git("worktree", "add", "-b", new_branch, target_path, base, capture=True)
    else:
        git("worktree", "add", "-b", new_branch, target_path, capture=True)

    return finish_new_worktree(target_path, main_worktree_root, new_mode)


def do_checkout_ref(
    ref: str,
    repo_base: str,
    main_worktree_root: str | None,
    default_branch: str | None,
    new_mode: NewMode | None,
) -> str:
    existing = find_worktree_for_local_branch(ref)
    if existing:
        return emit_path(existing, new_mode)

    if ref == default_branch and main_worktree_root:
        git("-C", main_worktree_root, "checkout", ref, capture=True)
        return emit_path(main_worktree_root, new_mode)

    target_path = target_dir_for(ref, repo_base)

    if git_check("show-ref", "--verify", "--quiet", f"refs/heads/{ref}"):
        git("worktree", "add", target_path, ref, capture=True)
        return finish_new_worktree(target_path, main_worktree_root, new_mode)

    result = git("branch", "-r", "--list", f"*/{ref}", capture=True, check=True)
    remote_matches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if remote_matches:
        tracking = remote_matches[0]
        git("worktree", "add", "-b", ref, target_path, tracking, capture=True)
        return finish_new_worktree(target_path, main_worktree_root, new_mode)

    if git_check("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"):
        git("worktree", "add", target_path, ref, capture=True)
        return finish_new_worktree(target_path, main_worktree_root, new_mode)

    raise GwError(f"gw: error: pathspec '{ref}' did not match any branch or ref")


def build_parser(prog_name: str = "gw") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Git worktree helper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Behavior:
  gw [-new {tab,window,split-h,split-v}] <branch-or-ref>
  gw [-new {tab,window,split-h,split-v}] [-base <branch>] -b <new-branch>
  gw -d <branch>
  gw -D <branch>

Notes:
  Successful checkout/create operations print the worktree path to stdout.
  The optional shell helpers in contrib/ can use that path to cd automatically.
""",
    )
    parser.add_argument(
        "--print-shell-integration",
        choices=["zsh", "bash"],
        help="print the shell helper for the selected shell",
    )
    parser.add_argument(
        "-new",
        dest="new_mode",
        default=None,
        choices=[mode.value for mode in NewMode],
        help="open the worktree in a new iTerm2 tab/window/split pane",
    )
    parser.add_argument(
        "-base",
        metavar="BRANCH",
        dest="base",
        help="update base branch (fetch/prune + cleanup) before creating a new branch",
    )

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-b", metavar="BRANCH", dest="create", help="create new branch and worktree")
    group.add_argument("-d", metavar="BRANCH", dest="delete", help="remove worktree and delete branch safely")
    group.add_argument("-D", metavar="BRANCH", dest="force_delete", help="force-remove worktree and branch")
    group.add_argument("ref", nargs="?", help="branch or ref to checkout")
    return parser


def validate_new_mode(new_mode: NewMode | None) -> None:
    if not new_mode:
        return
    if sys.platform != "darwin":
        raise GwError("gw: -new requires macOS (osascript)")
    if shutil.which("osascript") is None:
        raise GwError("gw: -new requires osascript (not found in PATH)")
    result = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to get name of every process'],
        capture_output=True,
        text=True,
        check=False,
    )
    if "iTerm2" not in (result.stdout or ""):
        raise GwError("gw: -new requires iTerm2 to be running")


def run(argv: list[str] | None = None, prog_name: str | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "co":
        argv.pop(0)

    program = prog_name or Path(sys.argv[0]).name or "gw"
    parser = build_parser(program)
    args = parser.parse_args(argv)

    try:
        if args.print_shell_integration:
            print(ZSH_INTEGRATION if args.print_shell_integration == "zsh" else BASH_INTEGRATION, end="")
            return 0

        if not any((args.create, args.delete, args.force_delete, args.ref)):
            parser.error("one of the arguments -b -d -D ref is required")

        _, repo_base, main_worktree_root = get_repo_info()
        default_branch = get_default_branch()
        new_mode = NewMode(args.new_mode) if args.new_mode else None
        validate_new_mode(new_mode)

        if args.base and not args.create:
            raise GwError("gw: -base can only be used with -b")

        output = ""
        if args.delete:
            do_delete(args.delete, force=False)
        elif args.force_delete:
            do_delete(args.force_delete, force=True)
        elif args.create:
            if args.base:
                update_base_branch(args.base, main_worktree_root)
            output = do_create_branch(args.create, args.base, repo_base, main_worktree_root, new_mode)
        else:
            output = do_checkout_ref(args.ref, repo_base, main_worktree_root, default_branch, new_mode)
    except GwError as exc:
        err(str(exc))
        return 1
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip()
        err(message if message else f"gw: git command failed: {' '.join(exc.cmd)}")
        return 1

    if output:
        print(output)
    return 0


def main() -> int:
    return run()
