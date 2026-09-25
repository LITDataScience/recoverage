# Roadmap

Order is from `docs/CRITIC.md`. The bug scoreboard is done. What is left before an upload is [pypi.md](pypi.md): the PyPI trusted publisher and a GitHub Release. There is still no OS container. The project page has to say so.

## Done in this pass

- **CRIT-03.** `decide_gate` blocks when runtime coverage was measured and `tests_exit_code` is not 0. The gate sentence says `the test run exited N`. Named thresholds (`merge-ready`, `production-ready`) fail. A numeric `--threshold` still compares MRS only.
- **CRIT-04, partial.** The CLI defaults to offline. `--llm` is required even when `RECOVERAGE_LLM_API_KEY` is set. `--no-llm` is an alias of the default. Non-HTTPS base URLs are rejected except loopback. SBST catches a failed LLM call and falls back to AST constants. Still open: payload minimization, response size limits, redirect checks, and a preview of the exact body before send. Library `llm_mode="auto"` is unchanged.
- **HIGH-09.** `.github/workflows/ci.yml` tests 3.11, 3.12, and 3.13 and runs `twine check` on the built distributions. The 3.8–3.10 pylint workflow is gone.
- **Sample report.** `examples/sample-report/analysis.json` and `report.md` no longer contain `/agent/recoverage/...`.

## Before the upload

- Create the PyPI trusted publisher and the GitHub environment `pypi`. Cut a release from the **Release** workflow (`.github/workflows/release.yml`). That publishes the GitHub Release, and `python-publish.yml` uploads it. Steps are in [pypi.md](pypi.md).
- Do not describe `--dynamic` as sandboxed. The README states the limit: trusted trees, static default, no OS container.

## P1

- **HIGH-05.** Fast vs deep mode. Each engine selectable and time-bounded. Sparse PageRank dangling-mass (one scalar per iteration, not a loop over every node). Cache parses by content hash. Benchmarks at 1k/10k/100k files before any performance claim.
- **HIGH-06.** Probes out of process. Until then, a real lock around `_DEPTH`, and `finally` restoration of `sys.path`, `sys.modules`, and the trace hook.
- **HIGH-07.** Unique temp coverage directory per run. Require the fresh report file. Never read a leftover `js-coverage/*.json`.
- **MED-01.** Core install plus extras (`python-coverage`, `javascript`, `graphs`, `pdf`, `dev`). `--no-pdf` so a missing Typst binary does not turn a finished analysis into exit 2.
- **MED-02.** One version source (`pyproject.toml` and `src/recoverage/version.py` are both `0.1.0` today). Classifiers, project URLs. Confirm sdist and wheel file lists in CI.

## P2

- **MED-03.** Escape or strictly render Markdown. Hostile strings in report tests.
- **MED-04.** Schema, version, and size checks on `analysis.json`. Reject symlinks that leave the project root. Atomic writes.
- **MED-05.** Trust manifest package roots and the configured test script. Suffix path matching should become unknown, not a guess. Fixtures for namespace packages, monorepos, mixed languages, duplicate basenames.

## Explicitly not the next step

Do not describe the temp copy as a sandbox. Do not upload a wheel that `python-publish.yml` did not build.
