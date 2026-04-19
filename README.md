# gwork

`gwork` is a small Git worktree helper for the flows that happen all day in active repositories:

- jump into an existing branch worktree
- create a new branch in its own worktree
- materialize a remote branch into a local worktree
- delete a branch and its worktree together

The core CLI works anywhere Git and Python 3.10+ work. The `-new` flag is an optional macOS-only convenience for opening the target worktree in iTerm2.

## Install

### PyPI

```bash
pipx install gwork
uv tool install gwork
```

Highly recommended next step after `uv tool install`:

```bash
gwork --install-shell-integration
```

That installs the `gw` shell helper so `gw <branch>` can switch worktrees and immediately `cd` into the result. Without shell integration, `gwork` still works, but it only prints the resolved path.

Transient execution is also supported:

```bash
uvx gwork --help
```

### From GitHub

```bash
pipx install git+https://github.com/v-ahuja/gw.git
uv tool install git+https://github.com/v-ahuja/gw.git
uvx --from git+https://github.com/v-ahuja/gw.git gwork --help
```

Highly recommended next step after `uv tool install`:

```bash
gwork --install-shell-integration
```

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
gwork --install-shell-integration gw
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

## Manual includes

If the repository root contains `.gw/includes/manual_includes`, `gwork` copies the `.gw/` directory and any files matching those patterns into newly created worktrees. This is useful for local ignored files such as `.env`, `*.local`, or `config/.env.*`.

Patterns use shell-style globs. Git-ignored directories are pruned while scanning so large ignored trees like `node_modules/` are skipped.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests
```

## License

MIT
