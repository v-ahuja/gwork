# Release process

Releases use two GitHub Actions workflows:

- `prepare release` updates both version declarations, performs the release
  checks, and opens a pull request against `main`.
- `release` detects a merged version bump on `main`, tags the commit, publishes
  the package to PyPI, and creates the GitHub Release.

## One-time setup

In the repository's **Settings → Actions → General → Workflow permissions**,
enable **Allow GitHub Actions to create and approve pull requests**. The
workflow has only the `contents: write` and `pull-requests: write` permissions
needed to push its release branch and open the pull request.

The `gwork` project on PyPI must have a GitHub trusted publisher configured for
owner `v-ahuja`, repository `gwork`, and workflow `release.yml`. No PyPI API
token or GitHub secret is needed. The publishing job receives only the
`id-token: write` permission required for PyPI's short-lived OIDC credentials.

## Prepare a release

1. Make sure all intended changes have been merged into `main` and CI is green.
2. On GitHub, open **Actions → prepare release → Run workflow**.
3. Enter the new canonical [PEP 440](https://peps.python.org/pep-0440/)
   version, such as `0.1.3`, and run the workflow.
4. Review and merge the pull request. The merge triggers the `release` workflow;
   no additional release command is required.

The workflow rejects a version that is invalid, is not greater than the current
version, already has a `v<version>` Git tag, or is already present on PyPI. It
then updates `pyproject.toml` and `src/gw/__init__.py` and runs:

- the unit test suite;
- smoke tests for both installed entry points;
- bash, zsh, and fish integration syntax and generated-file checks;
- wheel and source-distribution builds;
- strict `twine` metadata validation; and
- a clean wheel installation with version and entry-point checks.

If a release branch with the same version already exists, use its existing pull
request. After closing an abandoned release PR, delete its remote branch before
running the workflow again.

## Automatic publication after merge

The merge to `main` changes the version files and automatically triggers
`.github/workflows/release.yml`. The workflow:

- compares the merged version with the version before the merge and requires an
  increase;
- requires canonical, matching versions in `pyproject.toml` and
  `src/gw/__init__.py`;
- rejects versions already tagged or published on PyPI;
- runs the tests and entry-point smoke checks;
- builds and validates the wheel and source distribution;
- tags the exact merged commit as `v<version>`;
- publishes both files to PyPI through trusted publishing; and
- creates a GitHub Release with generated release notes.

Watch the `release` workflow after merging, then verify the package after it
succeeds:

```bash
uvx --from gwork==0.1.3 gwork --help
```

PyPI files are immutable. If publication fails before PyPI accepts any files,
rerun only the failed GitHub Actions jobs so the successful tag and build jobs
are not repeated. If PyPI accepted any files, inspect the project release before
retrying. If published files need correction, prepare a new patch version rather
than changing files under the published version.
