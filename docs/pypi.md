# Publishing to PyPI

The project on PyPI is [coderecoverage](https://pypi.org/project/coderecoverage/). `0.1.0` is the release that is live. This checkout is `0.2.0` and stays under `## [Unreleased]` until the next **Release** run. `pip install coderecoverage` installs the `recoverage` module and the `recoverage` command. The name `recoverage` was already taken, so it is not the distribution name.

The workflow that uploads is `.github/workflows/python-publish.yml`. It runs when a GitHub Release is published, and the Release workflow also starts it with `workflow_dispatch` on the version tag. A dispatch whose ref is `main` is rejected by the `pypi` environment, which allows only `v*` tags. The job tests 3.11, 3.12, and 3.13, builds the sdist and wheel, runs `twine check`, installs that wheel in a clean venv, smokes `recoverage --version`, lists archive members, scans the archives for secret-shaped tokens, and uploads that `dist/` with PyPI trusted publishing.

Do not upload a wheel built on a laptop. The files on PyPI have to be the artifact that job tested.

## Account setup

This is already done for `coderecoverage`. It is recorded here so the next publisher does not redo it on the wrong project name.

1. PyPI project: `coderecoverage`. Trusted publisher: owner `LITDataScience`, repository `recoverage`, workflow `python-publish.yml`, environment `pypi`.
2. GitHub environment `pypi`: required reviewer `LITDataScience`, deployment branches and tags limited to tags matching `v*`, no secrets. The workflow's publish job requires that environment name. `id-token: write` is only on that job.

## Cutting a release

Do this from GitHub. Do not `git tag` on a laptop. `python-publish.yml` refuses a release whose tag is not `v` plus `src/recoverage/version.py`, and it builds the files it uploads.

1. Put the notes under `## [Unreleased]` in `docs/CHANGELOG.md`. The Release workflow exits if that section is empty.
2. Set `__version__` in `src/recoverage/version.py` to the version you are shipping. One source. The tag will be `v` plus that string. For the dashboard release that string is `0.2.0`, and the notes are already under Unreleased.
3. Commit both to `main`. Wait until `.github/workflows/ci.yml` is green on that commit. That workflow also runs `mkdocs build --strict`.
4. Actions → **Release** → **Run workflow** → branch `main`. That workflow moves the Unreleased notes under `## [x.y.z] - date`, commits, pushes `vX.Y.Z`, publishes the GitHub Release, and starts `python-publish.yml` on that tag.
5. Approve the `pypi` environment deployment. Confirm the files on PyPI are the ones that job uploaded.

`GITHUB_TOKEN` releases do not start other workflows by themselves. The Release workflow dispatches the publish workflow on the tag for that reason.

The project page text is `README.md`. It has to say: trusted trees, default `run` does not execute code, `--dynamic` runs the checkout as you, and there is no OS sandbox.
