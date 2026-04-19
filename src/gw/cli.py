"""CLI implementation for gwork."""

from __future__ import annotations

import argparse
import enum
import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


class NewMode(enum.Enum):
    TAB = "tab"
    WINDOW = "window"
    SPLIT_H = "split-h"
    SPLIT_V = "split-v"


class GwError(RuntimeError):
    """Raised for user-facing gwork failures."""


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

DEFAULT_SHELL_ALIAS = "gw"
SHELL_FUNCTION_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ZSH_INTEGRATION_TEMPLATE = """__ALIAS__() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    command __COMMAND_NAME__ --help
    return $?
  fi

  local path rc
  path="$(command __COMMAND_NAME__ "$@")"
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
      '--install-shell-integration:append shell integration to your shell rc file'
      '--shell-integration-alias:override shell helper name for printed integration'
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

__ZSH_COMPLETION_DEFS__
_git_gwork() { _gw_complete "$@"; }
"""

BASH_INTEGRATION_TEMPLATE = """__ALIAS__() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    command __COMMAND_NAME__ --help
    return $?
  fi

  local path rc
  path="$(command __COMMAND_NAME__ "$@")"
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
    COMPREPLY=( $(compgen -W "--print-shell-integration --install-shell-integration --shell-integration-alias -new -b -base -d -D" -- "$cur") )
    return
  fi

  local local_branches remote_branches
  local_branches="$(git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null)"
  remote_branches="$(git for-each-ref --format='%(refname:lstrip=3)' refs/remotes/ 2>/dev/null | grep -v '^HEAD$' | sort -u)"
  COMPREPLY=( $(compgen -W "co ${local_branches} ${remote_branches}" -- "$cur") )
}

__BASH_COMPLETION_DEFS__
"""

SHELL_RC_FILES = {
    "zsh": ".zshrc",
    "bash": ".bashrc",
}

INSTALL_MARKER_START = "# >>> gwork shell integration >>>"
INSTALL_MARKER_END = "# <<< gwork shell integration <<<"


def err(message: str) -> None:
    print(message, file=sys.stderr)


def integration_script_for(shell: str, command_name: str, alias: str) -> str:
    targets = [alias]
    if command_name not in targets:
        targets.append(command_name)

    if shell == "zsh":
        completion_defs = "\n".join(f"compdef _gw_complete {target}" for target in targets)
        completion_defs += "\ncompdef _gw_complete git-gwork"
        return (
            ZSH_INTEGRATION_TEMPLATE.replace("__ALIAS__", alias)
            .replace("__COMMAND_NAME__", command_name)
            .replace("__ZSH_COMPLETION_DEFS__", completion_defs)
        )

    completion_defs = "\n".join(f"complete -F _gw_complete {target}" for target in targets)
    completion_defs += "\ncomplete -F _gw_complete git-gwork"
    return (
        BASH_INTEGRATION_TEMPLATE.replace("__ALIAS__", alias)
        .replace("__COMMAND_NAME__", command_name)
        .replace("__BASH_COMPLETION_DEFS__", completion_defs)
    )


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
        err("gwork: copied .gw/")

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
        err(f"gwork: copied {copied} file(s) from .gw/includes/manual_includes")


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
            "gwork: BASE_WORKTREE is not set.\n\n"
            "Create a base directory for worktrees and export it in your shell config:\n\n"
            '  mkdir -p "$HOME/worktrees"\n'
            '  export BASE_WORKTREE="$HOME/worktrees"\n'
        )

    if not os.path.isdir(base_worktree):
        raise GwError(
            f"gwork: BASE_WORKTREE '{base_worktree}' does not exist. Create it first:\n"
            f'  mkdir -p "{base_worktree}"'
        )

    if not git_check("rev-parse", "--is-inside-work-tree"):
        raise GwError("gwork: not inside a git repo.")

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
            raise GwError(f"gwork: base branch '{base}' not found")
        if main_worktree_root:
            git("-C", main_worktree_root, "checkout", base, capture=True)
            worktree_path = main_worktree_root
        else:
            raise GwError(f"gwork: base branch '{base}' has no worktree and no main worktree is available")

    err("gwork: cleaning up gone branches...")
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
        err(f"gwork: deleted gone branch '{branch_name}'")


def do_delete(branch: str, force: bool) -> None:
    worktree_path = find_worktree_for_local_branch(branch)
    branch_exists = git_check("show-ref", "--verify", "--quiet", f"refs/heads/{branch}")

    if not worktree_path and not branch_exists:
        raise GwError(f"gwork: branch '{branch}' not found")

    if not force and branch_exists:
        result = git("branch", "-d", branch, capture=True, check=False)
        if result.returncode != 0:
            stderr = result.stderr or ""
            if "used by worktree" in stderr:
                merged = git("merge-base", "--is-ancestor", branch, "HEAD", check=False)
                if merged.returncode != 0:
                    raise GwError(f"gwork: branch '{branch}' is not fully merged (use -D to force)")
            else:
                raise GwError(stderr.rstrip())
        else:
            branch_exists = False

    if worktree_path:
        if force:
            git("worktree", "remove", "--force", worktree_path)
        else:
            git("worktree", "remove", worktree_path)
        err(f"gwork: removed worktree '{worktree_path}'")

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
        raise GwError(f"gwork: branch '{new_branch}' already exists (use gwork '{new_branch}')")

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

    raise GwError(f"gwork: error: pathspec '{ref}' did not match any branch or ref")


def build_parser(prog_name: str = "gwork") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Git worktree helper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Behavior:
  gwork [-new {tab,window,split-h,split-v}] <branch-or-ref>
  gwork [-new {tab,window,split-h,split-v}] [-base <branch>] -b <new-branch>
  gwork -d <branch>
  gwork -D <branch>

Notes:
  Successful checkout/create operations print the worktree path to stdout.
  Shell integration uses that path to change your current shell into the
  resolved worktree after switching to a worktree or creating a new one.

Shell integration:
  gwork --install-shell-integration gw
  gwork --print-shell-integration [zsh|bash]
  gwork --print-shell-integration zsh --shell-integration-alias gw
""",
    )
    parser.add_argument(
        "--print-shell-integration",
        nargs="?",
        const="auto",
        metavar="SHELL",
        help="print the shell helper for zsh/bash, or infer it from $SHELL when omitted",
    )
    parser.add_argument(
        "--install-shell-integration",
        nargs="?",
        const="prompt",
        metavar="NAME",
        help=(
            "append shell integration to your shell rc file; when NAME is omitted, "
            f"prompt interactively and default to {DEFAULT_SHELL_ALIAS}"
        ),
    )
    parser.add_argument(
        "--shell-integration-alias",
        default=DEFAULT_SHELL_ALIAS,
        metavar="NAME",
        help=f"shell function name to install/print for integration helpers (default: {DEFAULT_SHELL_ALIAS})",
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
        raise GwError("gwork: -new requires macOS (osascript)")
    if shutil.which("osascript") is None:
        raise GwError("gwork: -new requires osascript (not found in PATH)")
    result = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to get name of every process'],
        capture_output=True,
        text=True,
        check=False,
    )
    if "iTerm2" not in (result.stdout or ""):
        raise GwError("gwork: -new requires iTerm2 to be running")


def resolve_integration_shell(value: str) -> str:
    if value in {"zsh", "bash"}:
        return value
    if value != "auto":
        raise GwError(f"gwork: unsupported shell integration target '{value}' (expected zsh or bash)")

    shell = Path(os.environ.get("SHELL", "")).name
    if shell in {"zsh", "bash"}:
        return shell

    raise GwError("gwork: could not infer shell from $SHELL (specify 'zsh' or 'bash')")


def resolve_integration_alias(value: str) -> str:
    if SHELL_FUNCTION_NAME_RE.match(value):
        return value
    raise GwError(
        f"gwork: unsupported shell integration alias '{value}' "
        "(expected a shell function name like 'gw' or 'gwork')"
    )


def prompt_for_integration_alias() -> str:
    response = input(f"gwork shell integration alias [{DEFAULT_SHELL_ALIAS}]: ").strip()
    return response or DEFAULT_SHELL_ALIAS


def install_shell_integration(shell: str, command_name: str, alias: str) -> None:
    rc_path = Path.home() / SHELL_RC_FILES[shell]
    block = "\n".join(
        [
            INSTALL_MARKER_START,
            "# Managed by gwork.",
            integration_script_for(shell, command_name, alias).rstrip(),
            INSTALL_MARKER_END,
            "",
        ]
    )

    existing = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
    kept_lines: list[str] = []
    in_managed_block = False

    for line in existing.splitlines():
        if line == INSTALL_MARKER_START:
            in_managed_block = True
            continue
        if line == INSTALL_MARKER_END:
            in_managed_block = False
            continue
        if not in_managed_block:
            kept_lines.append(line)

    content = "\n".join(kept_lines).rstrip()
    if content:
        content = f"{content}\n\n{block}"
    else:
        content = block

    rc_path.write_text(content, encoding="utf-8")
    err(f"gwork: installed shell integration in '{rc_path}'")
    err(f"gwork: run 'source {rc_path}' or open a new {shell} session")


def run(argv: list[str] | None = None, prog_name: str | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "co":
        argv.pop(0)

    program = prog_name or Path(sys.argv[0]).name or "gwork"
    parser = build_parser(program)
    args = parser.parse_args(argv)

    try:
        if args.print_shell_integration:
            integration_alias = resolve_integration_alias(args.shell_integration_alias)
            shell = resolve_integration_shell(args.print_shell_integration)
            print(integration_script_for(shell, program, integration_alias), end="")
            return 0

        if args.install_shell_integration:
            integration_alias_value = args.install_shell_integration
            if integration_alias_value == "prompt":
                integration_alias_value = prompt_for_integration_alias()
            integration_alias = resolve_integration_alias(integration_alias_value)
            shell = resolve_integration_shell("auto")
            install_shell_integration(shell, program, integration_alias)
            return 0

        if not any((args.create, args.delete, args.force_delete, args.ref)):
            parser.error("one of the arguments -b -d -D ref is required")

        _, repo_base, main_worktree_root = get_repo_info()
        default_branch = get_default_branch()
        new_mode = NewMode(args.new_mode) if args.new_mode else None
        validate_new_mode(new_mode)

        if args.base and not args.create:
            raise GwError("gwork: -base can only be used with -b")

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
        err(message if message else f"gwork: git command failed: {' '.join(exc.cmd)}")
        return 1

    if output:
        print(output)
    return 0


def main() -> int:
    return run()
