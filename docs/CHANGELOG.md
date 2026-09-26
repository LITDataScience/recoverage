# Changelog

All notable changes are documented here. The format is [Keep a Changelog](https://keepachangelog.com/).

`## [Unreleased]` is what the next tag will contain. The Release workflow moves those notes under `## [x.y.z] - date`, tags `v{x.y.z}` from `src/recoverage/version.py`, and publishes the GitHub Release that uploads to PyPI. Bump `version.py` in the same commit as the notes.

## [Unreleased]

- `report.html` is a single-file dashboard: inline SVG charts, filters, a theme toggle, and a file table. It does not load a network resource. A missing matplotlib install still draws the charts.
- Walk size, cache, and the run budget follow the machine: halved under 4 GB of RAM, deep probes skipped under 2 GB, temp copies skipped when the temp volume has under 1 GB free. A GPU is not used and not required.
- The shop fixture tests cover payments, pricing, and the cart branches. A `--dynamic --deep` sample scores MRS 95, gate `production-ready`, statement coverage 100%. Property rows count only decided trials. A longer list is not timed as an 8x regression. The detected test runner is not a phantom import. Typst is also found in the WinGet links directory when it is not on `PATH`.
- Pytest `addopts` from the project are not passed through. A `--cov` flag there makes pytest exit 4 under `coverage run` when pytest-cov is absent. Exit 4 also covers a `conftest.py` that cannot import, which happens when Recoverage's interpreter is not the project's. Coverage stays unmeasured and the note names the missing module. The traceback is not stored.
- Documentation is an MkDocs Material site, built in CI and published to GitHub Pages, with a PDF. `recoverage docs` opens it.
- The Release workflow starts the PyPI upload on the version tag. The `pypi` environment rejects a run whose ref is `main`.

## [0.1.0] - 2026-09-25

- Default `run` is static. `--dynamic` opts into tests. `--deep` opts into property, mutation, timing, and search probes, all outside this process. Child environments are an allowlist. Timeouts kill the process tree.
- `analysis.json` is scrubbed and written compact. Search arguments are type names. Gap text is escaped in Markdown. A loaded analysis must match this version and stay under 100 MB.
- Performance pass. Each source file is read once and parsed once per run (`sources.SourceCache`). Coverage pairing, call-edge resolution, graph queries, blast radius, gap lookups, and JS line numbers are indexed instead of scanned: O(S·F), O(E·V), O(V+E) per query, O(F·T), and O(n²) loops are gone. PageRank stops on convergence. A static run over a 2_000-module, 20_000-function tree went from 67s to 24s on the same machine; the file-read count fell from about 6_600 to 2_200. With no diff, `analytics.blast.radius` is `[]` and `radius_size` carries the count.
- Temp copies for `generate` and mutation copy symlinks as links and skip `.git`, `node_modules`, `.venv`, `.tox`, and caches. Coverage temp directories are removed after every run. The MCP `serverInfo.version` reads `recoverage.version`.
- Missing Typst no longer fails the command after Markdown and HTML exist. The required install dependency is `coverage`. Matplotlib and Tree-sitter are the `report` extra.
- The README is the PyPI description: trusted trees, no OS sandbox. Publish steps are in `docs/pypi.md`.
- The gate is `blocked` when runtime coverage was measured and the test runner did not exit 0. The gate sentence includes `the test run exited N`. The rubric's blocked row matches. A numeric `--threshold` fails when the tests failed.
- The CLI no longer contacts an LLM just because `RECOVERAGE_LLM_API_KEY` is set. Pass `--llm`. Responses are capped and redirects are refused. Library `llm_mode` `"auto"` stays offline.
- `examples/sample-report/` no longer embeds the `/agent/recoverage/...` build path.
- CI runs pytest on Python 3.11, 3.12, and 3.13, with Typst installed, and checks the built wheel and sdist with `twine`. The pylint workflow that targeted 3.8–3.10 is removed.
- Documentation lives in `docs/`. The root README is the short entry point and still embeds the rubric verbatim.
- The PyPI distribution name is `coderecoverage`. `recoverage` was already registered. The import and the `recoverage` command are unchanged.
- Drafted property tests are plain pytest. They no longer import Hypothesis, which a normal install does not have, so the temp-copy filter was deleting every draft.
- `.github/workflows/release.yml` is the only way to tag. It promotes this file, tags `v` plus `version.py`, and publishes the GitHub Release. `python-publish.yml` refuses a tag that does not match `version.py`, then uploads that commit to PyPI.
