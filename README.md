# gwork

`gwork` is a small Git worktree helper for the flows that happen all day in active repositories:

- jump into an existing branch worktree
- create a new branch in its own worktree
- materialize a remote branch into a local worktree
- delete a branch and its worktree together

The core CLI works anywhere Git and Python 3.10+ work. The `-new` flag is an optional macOS-only convenience for opening the target worktree in iTerm2.

New to worktrees? See [docs/worktrees.md](docs/worktrees.md) for a plain-English explanation and the full case for why gwork exists.

Also check out https://worktrunk.dev/, for more / slightly different worktree management workflows.

## Why gwork

Git worktrees let each branch live in its own folder so you can work on multiple branches simultaneously — no stashing, no context switching. This is especially powerful with coding agents, where you can run several agents on separate features or fixes at the same time, each in its own isolated environment.

The raw Git commands add up fast. Without gwork, creating a new worktree means running `git worktree add`, manually `cd`-ing to the path, and copying over any local config files by hand. Switching to an existing one means running `git worktree list` to find the path, then `cd`-ing there yourself.

With gwork:

```bash
gw feature/auth          # jump to (or create) a worktree for this branch
gw -b feature/new-thing  # new branch in its own worktree
gw -d feature/old-thing  # delete worktree and branch together
```

One command handles the path, the `git worktree` plumbing, and copies files like `.env` automatically. With shell integration, it also `cd`s you straight into the result.

→ Full breakdown with side-by-side comparisons: [docs/worktrees.md](docs/worktrees.md)

## Install

### From PyPI

```bash
pipx install gwork
uv tool install gwork
uvx gwork --help
```

`pip install gwork` also works, but `pipx` or `uv tool install` keeps CLI tools isolated from project environments.

### From GitHub

```bash
pipx install git+https://github.com/v-ahuja/gwork.git
uv tool install git+https://github.com/v-ahuja/gwork.git
uvx --from git+https://github.com/v-ahuja/gwork.git gwork --help
```

Highly recommended next step after `uv tool install`:

```bash
gwork --install-shell-integration
```

That installs the `gwork` shell helper so `gwork <branch>` can switch worktrees and immediately `cd` into the result. Without shell integration, `gwork` still works, but it only prints the resolved path.

## Required setup

Create a directory where `gwork` can place per-repo worktrees and export it in your shell startup:

```bash
mkdir -p "$HOME/worktrees"
export BASE_WORKTREE="$HOME/worktrees"
```

`BASE_WORKTREE` is required. `gwork` organizes worktrees under it by repository name.

## Usage

Note: actual name here depends on the shell integration step. E.g. If you've named it `gw` then all commands below should be `gw` instead of `gwork`.

```bash
gwork main
gwork feature/foo
gwork -b feature/new-thing
gwork -base main -b feature/from-main
gwork -d feature/old-thing
gwork -D feature/broken-thing
git gwork feature/foo
```

Successful checkout and branch-creation commands print the absolute worktree path to stdout. That makes the plain CLI useful in scripts and also lets the shell helper `cd` automatically.

### Shell integration (Highly recommended)

The CLI itself cannot change your current shell directory. If you want `gwork` to drop you directly into the returned worktree, source the generated helper:

```bash
gwork --install-shell-integration
gwork --install-shell-integration gw # if you want to name the shell integration `gw` instead. shorter and easier.
gwork --install-shell-integration gwork

# manual sourcing still works
source <(gwork --print-shell-integration)
source <(gwork --print-shell-integration zsh)
source <(gwork --print-shell-integration bash)
source <(gwork --print-shell-integration zsh --shell-integration-alias gwork)
```

`--install-shell-integration` appends a managed block to `~/.zshrc` or `~/.bashrc` and infers the shell from `$SHELL`. When you omit the alias, it prompts interactively and defaults to `gw` if you just hit Enter. Passing a name explicitly still works for scripting. `--shell-integration-alias` still applies to `--print-shell-integration` when you want to generate a different helper script without installing it.

The helper:

- runs the `gwork` CLI
- captures the printed worktree path
- changes your current shell directory into the resolved worktree after switching to one or creating a new one
- enables completion

The repository also includes checked-in copies under `contrib/` for users who prefer to source a file directly.

## macOS `-new`

`-new {tab,window,split-h,split-v}` opens the target worktree in iTerm2 via `osascript`. This mode is only supported on macOS, requires `osascript` on `PATH`, and requires iTerm2 to be running.

## Worktree config and setup

The `.gw` folder contains the local repo config for `gwork`. Global/User level settings support will come shortly. The `.gw` folder is always copied when a new worktree is created.

The `.gw/includes/manual_worktree` file lets you copy more things when a new worktree is created. It

Currently, there's just one supported config - `manual_includes`. The `manual_includes` file is useful for automatically. This is useful for local ignored files such as `.env`, `*.local`, or `config/.env.*`.

Patterns use shell-style globs. Git-ignored directories are pruned while scanning so large ignored trees like `node_modules/` are skipped.

E.g file

```zsh
# .gw/includes/manual_worktree
.env
.credentials
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests
```

## License

MIT
