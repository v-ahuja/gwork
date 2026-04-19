# gw

`gw` is a small Git worktree helper for the flows that happen all day in active repositories:

- jump into an existing branch worktree
- create a new branch in its own worktree
- materialize a remote branch into a local worktree
- delete a branch and its worktree together

The core CLI works anywhere Git and Python 3.10+ work. The `-new` flag is an optional macOS-only convenience for opening the target worktree in iTerm2.

## Install

### PyPI

```bash
pipx install gw
uv tool install gw
```

Transient execution is also supported:

```bash
uvx gw --help
```

### From GitHub

```bash
pipx install git+https://github.com/v-ahuja/gw.git
uv tool install git+https://github.com/v-ahuja/gw.git
uvx --from git+https://github.com/v-ahuja/gw.git gw --help
```

## Required setup

Create a directory where `gw` can place per-repo worktrees and export it in your shell startup:

```bash
mkdir -p "$HOME/worktrees"
export BASE_WORKTREE="$HOME/worktrees"
```

`BASE_WORKTREE` is required. `gw` organizes worktrees under it by repository name.

## Usage

```bash
gw main
gw feature/foo
gw -b feature/new-thing
gw -base main -b feature/from-main
gw -d feature/old-thing
gw -D feature/broken-thing
git gw feature/foo
```

Successful checkout and branch-creation commands print the absolute worktree path to stdout. That makes the plain CLI useful in scripts and also lets the shell helper `cd` automatically.

### Shell integration

The CLI itself cannot change your current shell directory. If you want `gw` to drop you directly into the returned worktree, source the generated helper:

```bash
source <(gw --print-shell-integration zsh)
# or
source <(gw --print-shell-integration bash)
```

The helper:

- runs the `gw` CLI
- captures the printed worktree path
- changes the current shell directory when appropriate
- enables completion

The repository also includes checked-in copies under `contrib/` for users who prefer to source a file directly.

## macOS `-new`

`-new {tab,window,split-h,split-v}` opens the target worktree in iTerm2 via `osascript`. This mode is only supported on macOS, requires `osascript` on `PATH`, and requires iTerm2 to be running.

## Manual includes

If the repository root contains `.gw/includes/manual_includes`, `gw` copies the `.gw/` directory and any files matching those patterns into newly created worktrees. This is useful for local ignored files such as `.env`, `*.local`, or `config/.env.*`.

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
