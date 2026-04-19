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
gw --help
git-gw --help
gw --print-shell-integration zsh >/dev/null
```

## Notes

- Tests create temporary Git repositories and configure their own local Git identity.
- `-new` is covered with mocks; CI does not require iTerm2.
