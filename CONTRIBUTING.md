# Contributing

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run tests

```bash
python -m unittest discover -s tests
```

## Packaging smoke checks

```bash
python -m build
python -m pip install -e .
gwork --help
git-gwork --help
gwork --print-shell-integration zsh >/dev/null
gwork --print-shell-integration bash >/dev/null
gwork --print-shell-integration fish >/dev/null
```

## Notes

- Tests create temporary Git repositories and configure their own local Git identity.
- `-new` is covered with mocks; CI does not require iTerm2.
- Shell integration supports zsh, bash, and fish. The fish helper needs its own
  template because fish is not POSIX-compatible — see the fish specifics in
  `AGENTS.md` before editing it.
- Tests that shell out to `fish` skip automatically when fish is not installed.
- The checked-in `contrib/gwork.*` helpers are generated from the templates in
  `src/gw/cli.py`, and CI fails if they drift. Regenerate them after template changes.
