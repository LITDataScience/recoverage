# Publishing to PyPI

The workflow that uploads is `.github/workflows/python-publish.yml`. It runs when a GitHub Release is published. It tests 3.11, 3.12, and 3.13, builds the sdist and wheel, runs `twine check`, installs that wheel in a clean venv, smokes `recoverage --version`, lists archive members, scans the archives for secret-shaped tokens, and uploads that `dist/` with PyPI trusted publishing.

Do not upload a wheel built on a laptop. The files on PyPI have to be the artifact that job tested.

## One-time account setup

This is not in the repo. Someone with the PyPI account has to do it once.

1. Create the PyPI project `recoverage` (or let the first trusted publish create it, if the account allows that).
2. On PyPI, add a trusted publisher: owner `LITDataScience`, repository `recoverage`, workflow `python-publish.yml`, environment `pypi`.
3. On GitHub, create an environment named `pypi`. The workflow's publish job requires that name. `id-token: write` is only on that job.

## Cutting a release

Do this from GitHub. Do not `git tag` on a laptop, and do not upload a wheel built on one. `python-publish.yml` refuses a release whose tag is not `v` plus `src/recoverage/version.py`, and it builds the files it uploads.

1. Put the notes under `## [Unreleased]` in `docs/CHANGELOG.md`.
2. Set `__version__` in `src/recoverage/version.py` to the version you are shipping. One source. The tag will be `v` plus that string.
3. Commit both to `main`. Wait until `.github/workflows/ci.yml` is green on that commit.
4. Actions → **Release** → **Run workflow** → branch `main`. That workflow moves the Unreleased notes under `## [x.y.z] - date`, commits, pushes `vX.Y.Z`, and publishes the GitHub Release.
5. Publishing the Release starts `python-publish.yml`. Confirm the files on PyPI are the ones that job uploaded.

The first run needs the trusted publisher and the `pypi` environment from the section above. Without them the Release is created and the publish job fails.

The project page text is `README.md`. It has to say: trusted trees, default `run` does not execute code, `--dynamic` runs the checkout as you, and there is no OS sandbox.
