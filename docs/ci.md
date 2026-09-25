# CI

Copy `examples/ci/recoverage.yml` to `.github/workflows/recoverage.yml` on a project you want to gate. The example fails the job when the result is below `--threshold merge-ready`. Change the threshold to `production-ready`, `needs-review`, `blocked`, or a number such as `70`.

Gate rank is `blocked` < `needs-review` < `merge-ready` < `production-ready`. A named gate is blocked when the project's own tests exit nonzero, so a red suite cannot clear `merge-ready`. A numeric threshold also fails when the test run failed.

The workflow's `pip install recoverage` line is for after this package is published. From a checkout of this repo, install with `pip install -e .` instead.

## Artifacts

The example uploads `report.md`, `report.pdf`, `charts/`, and `analysis.json`. `analysis.json` is scrubbed (basenames, blank docstrings, redacted secrets, type-name search args) and still contains relative paths and gap text. If the job's artifact store is broader than the people who can already read the repo, drop `analysis.json` from the upload. See [reports.md](reports.md) and [security.md](security.md).

The example checks out the project. Default `recoverage run` does not execute it. A workflow that passes `--dynamic` runs the tests as the job user. The child environment is an allowlist, not a copy of every secret, and that is still not a sandbox. Do not point `--dynamic` at a checkout you do not trust.

## This repository's own CI

`.github/workflows/ci.yml` tests Python 3.11, 3.12, and 3.13 (`pip install -e ".[dev]"`, Typst installed, `python -m pytest`) and builds a wheel plus sdist with `twine check`. It does not publish.

`.github/workflows/release.yml` is run by hand from the Actions tab, on `main` only. It promotes `## [Unreleased]` in `docs/CHANGELOG.md`, tags `v` plus `src/recoverage/version.py`, and publishes the GitHub Release. That is the only tag path.

`.github/workflows/python-publish.yml` tests, builds, installs the wheel, and uploads to PyPI with trusted publishing when a GitHub Release is published. It refuses a tag that does not match `version.py`. Actions are commit pins. The account steps are in [pypi.md](pypi.md). Do not upload a wheel built outside that workflow.
