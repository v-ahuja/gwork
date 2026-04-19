# AGENTS

## Project summary

`gw` is a Python CLI that wraps common `git worktree` workflows behind a smaller interface. Its main job is to resolve a branch or ref, ensure there is a corresponding worktree under a configured base directory, and return the resulting path. The CLI is cross-platform for core Git behavior. The `-new` flow is intentionally macOS+iTerm2-specific.

Primary user flows:

- `gw <branch-or-ref>`: reuse or create a worktree for an existing local branch, remote branch, or commit ref
- `gw -b <new-branch>`: create a new branch in its own worktree
- `gw -base <branch> -b <new-branch>`: update a base branch, prune gone branches, then branch from it
- `gw -d <branch>`: remove the worktree and delete the branch safely
- `gw -D <branch>`: force-remove the worktree and force-delete the branch
- `git gw ...`: same CLI through Git subcommand discovery

## How it works

The main implementation lives in [src/gw/cli.py](/Users/vina/software/config_test/gw/src/gw/cli.py).

Core behavior:

- `BASE_WORKTREE` is required and must point to an existing directory.
- Worktrees are organized under `BASE_WORKTREE/<repo-name>/`.
- Branch names are sanitized into directory names by replacing `/` with `__`.
- Successful checkout and branch-creation operations print the absolute worktree path to stdout.
- Delete operations print status to stderr/stdout and return success without printing a path.
- The plain CLI never changes the caller's shell directory; shell integration handles `cd`.

Repo detection and worktree layout:

- `gw` must be run inside a Git worktree.
- The tool distinguishes between the main worktree and linked worktrees using Git’s common dir.
- The default branch is detected from `refs/remotes/origin/HEAD` when available.
- If the requested ref is the default branch and the main worktree is available, `gw` reuses the main checkout instead of creating a second worktree for it.

Ref resolution order:

1. Existing local branch worktree
2. Default branch main worktree reuse
3. Local branch
4. Remote branch
5. Commit ref
6. Error if none match

Branch deletion semantics:

- Safe delete must not remove a worktree unless the branch is merge-safe.
- If `git branch -d` fails only because the branch is checked out in a worktree, `gw` explicitly checks merge ancestry before removing the worktree.
- `-D` skips that protection and force-removes both worktree and branch.

## Shell integration

`gw` supports optional shell bootstrap via:

- `gw --print-shell-integration zsh`
- `gw --print-shell-integration bash`

These helpers:

- call the `gw` CLI
- capture the printed path
- `cd` into that path on success
- install completion for `gw` and `git-gw`

Checked-in copies also exist under [contrib/gw.zsh](/Users/vina/software/config_test/gw/contrib/gw.zsh) and [contrib/gw.bash](/Users/vina/software/config_test/gw/contrib/gw.bash), but installed-package users should prefer `--print-shell-integration`.

## macOS-specific behavior

`-new {tab,window,split-h,split-v}` uses `osascript` to tell iTerm2 to open the resolved path in a new tab, window, or split. Important constraints:

- only supported on macOS
- requires `osascript` on `PATH`
- requires iTerm2 to be running
- does not print a path when it opens a new session

This logic is isolated in the AppleScript templates and `open_iterm()`.

## Manual includes

When creating a new worktree from the main worktree, `gw` copies local metadata from `.gw/` if present.

Important rules:

- the `.gw/` directory itself is copied wholesale
- `.gw/includes/manual_includes` can list glob patterns for additional files to copy
- comments and blank lines in `manual_includes` are ignored
- ignored directories are pruned using `git check-ignore`, so large trees like `node_modules/` are skipped
- matching supports filename-only globs and path-aware globs

This is intended for local ignored files such as `.env`, `*.local`, and similar per-worktree config.

## Packaging and entry points

The project is packaged as a normal Python CLI in [pyproject.toml](/Users/vina/software/config_test/gw/pyproject.toml).

Installed console scripts:

- `gw`
- `git-gw`

The package should remain compatible with:

- `pipx install gw`
- `uv tool install gw`
- `uvx gw`
- `pip install -e .` for local development

## Testing

Tests live in [tests/test_cli.py](/Users/vina/software/config_test/gw/tests/test_cli.py) and use `unittest` with temporary Git repositories.

Covered scenarios include:

- missing `BASE_WORKTREE`
- running outside a Git repo
- local branch reuse
- remote branch materialization
- commit ref checkout
- branch creation
- `-base` cleanup behavior
- safe delete vs force delete
- default branch main-worktree reuse
- manual include copying
- non-macOS rejection for `-new`
- mocked macOS `osascript` execution

Run tests with:

```bash
python -m unittest discover -s tests
```

## Change guidance for future agents

- Keep stdout reserved for the returned worktree path or explicit shell-integration output. User-facing diagnostics should go to stderr.
- Do not break the contract that shell helpers depend on: successful path-producing operations must print exactly one resolved path.
- Preserve cross-platform core behavior. macOS-only functionality should stay behind `-new`.
- Be careful when changing delete logic; safe delete must remain merge-safe before removing a worktree.
- Be careful when changing path handling; the CLI should continue emitting canonical absolute paths.
- If shell integration changes, update both the generated integration strings in `src/gw/cli.py` and the checked-in `contrib/` copies.
