# Recoverage: strict security, quality, and release review

Revision after the performance pass. Every module under `src/recoverage/` was re-read for complexity, redundant IO, temp-file hygiene, and symlink handling. The local suite is 55 unit tests plus 4 integration tests, all passing. `pyflakes` is clean over `src/` and `tests/`. No wheel or sdist was opened. GitHub Actions has not been observed running `ci.yml`. Line numbers below are from this revision of the tree.

## Production-ready?

**No. Do not publish this to PyPI yet.** The ship list below is in this tree. The remaining reason is the one CRIT-01 allowed as a fallback and did not remove: `--dynamic` and `--deep` run the checkout as the user, in a child process, with an environment allowlist and a process-tree kill. There is still no OS container. Default `run` does not execute the checkout.

`production-ready` inside a Recoverage report means "MRS cleared 85, with measured coverage and no critical gap." It does not mean this package is fit to ship. Those are different claims. The report badge is also not a security audit of the project under test.

A package that strangers `pip install` and point at arbitrary checkouts has to survive four facts:

1. The checkout can be hostile. Default `run` does not import it. `--dynamic` does, as the user, outside this process, without API, cloud, CI, or SSH keys. That is not a sandbox.
2. The output can be shared. `analysis.json` is scrubbed: docstrings blanked, absolute paths reduced to a basename, secret-shaped text redacted, SBST args stored as type names.
3. The score can be automated. A red suite, a missing exit code, an exception trial, and a timing run with no samples no longer award the points those factors name.
4. The published file has to be the tested file. `python-publish.yml` tests, builds, installs the wheel, smokes the CLI, lists archive members, scans for secret-shaped tokens, and uploads that artifact. Actions are pinned to commits. GitHub Actions has not been observed.

Docs in `docs/security.md` now say "trusted checkout only." A README warning is not an isolation boundary. People will not read it, and CI workflows will keep secrets in the environment anyway.

### What is required to publish to PyPI

The bug scoreboard is not the publish checklist. A wheel can be built today. Uploading it is a separate decision. `production-ready` on a report is not that decision.

Already in the tree: `pyproject.toml` (name `recoverage`, version from `version.py`, `requires-python >= 3.11`, MIT, README as the long description, classifiers, keywords, URLs, console script), `LICENSE`, and `.github/workflows/python-publish.yml`. That workflow tests 3.11–3.13, builds, runs `twine check`, installs the wheel in a clean venv, smokes `recoverage --version`, lists archive members, scans for secret-shaped tokens, and publishes with OIDC (`id-token: write` only on the publish job, environment `pypi`). Actions are commit pins. None of this has been observed on GitHub. No wheel from this revision was opened locally.

1. **PYPI-01.** Done. `README.md` says the default run is static, lists `--dynamic` and `--deep`, and says a missing Typst binary does not fail the command.
2. **PYPI-02.** Done. `docs/security.md` matches the current opt-in, allowlist, probe worker, scrub, and LLM cap.
3. **PYPI-03.** Done. The rubric says temp copy. The README embeds that rubric.
4. **PYPI-04.** Not done from this tree. Reserve the PyPI project `coderecoverage` (`recoverage` is taken). Add a trusted publisher for this repo, workflow `python-publish.yml`, and the GitHub environment `pypi`. Watch `ci.yml` go green. Publish by cutting a GitHub Release. Do not upload a wheel built on a laptop. Steps are in `docs/pypi.md`.
5. **PYPI-05.** Done as the allowed product decision. The first lines of the README say trusted trees, static default, `--dynamic` runs as you, no OS sandbox. There is still no container. Do not describe the package as a scanner for hostile repositories.

PYPI-04 is the remaining upload step. It is an account action, not a code change.

## Scoreboard

Status means the state of the fix, not the severity of the bug.

| Status | Meaning |
| --- | --- |
| DONE | The required change is in this tree and a test covers the behavior that was wrong. Residuals, if any, are called out and are not the original bug. |
| IN PROGRESS | Some of the required change is in this tree. The finding is not closed. |
| TODO | No code toward the required change. |

| ID | Priority | Status | What is still wrong |
| --- | --- | --- | --- |
| CRIT-01 | CRITICAL | DONE | Default `run` is static-only. `--dynamic` prints that there is no OS sandbox, uses an env allowlist, and kills the process tree. PBT, SBST, and timing run in `probe_worker`. Residual: no container. |
| CRIT-02 | CRITICAL | DONE | Persisted SBST args are type names. Secret-shaped strings become `<redacted>`. `analysis.json` is scrubbed before write. |
| CRIT-03 | CRITICAL | DONE | A measured run with exit code `None` is `blocked`. Any set threshold, including a number, fails when tests failed. Timeouts record exit 124. |
| CRIT-04 | HIGH | DONE | `auto` is offline. Response cap is 1_000_000 bytes. Redirects are refused. CLI still requires `--llm`. |
| HIGH-01 | HIGH | DONE | JSON scrub drops absolute paths and docstrings. Markdown prints the directory name. Test-log tails are not stored. |
| HIGH-02 | HIGH | DONE | Probe calls die at 2s. A timing batch dies at 30s inside the worker. Coverage and pytest kill the process tree. A run stops deep probes after 600s. |
| HIGH-03 | HIGH | DONE | `TypeError`, `ValueError`, `KeyError`, and `OverflowError` are invalid trials, not passes. |
| HIGH-04 | HIGH | DONE | Zero successful timing samples sets `ran` false, so the factor scores 0. |
| HIGH-05 | HIGH | DONE | PBT, mutation, timing, and SBST run only with `--deep`. PageRank uses one dangling-mass scalar per iteration. |
| HIGH-06 | HIGH | DONE | A lock rejects overlapping runs. PBT, SBST, and timing do not insert `sys.path` or import the project in this process. |
| HIGH-07 | HIGH | DONE | Python and JS coverage write to a fresh temp directory per run. |
| HIGH-08 | HIGH | DONE | Publish runs the suite, `twine check`, a clean wheel install, CLI smoke, archive listing, and a secret-token scan, then uploads that artifact. Actions are commit pins. |
| HIGH-09 | HIGH | DONE | CI matrix is 3.11, 3.12, 3.13 and runs pytest plus `twine check`. Not observed on GitHub. Actions are commit pins. |
| MED-01 | MEDIUM | DONE | Runtime dependency is `coverage`. Matplotlib and Tree-sitter are the `report` extra and are imported lazily. Missing Typst prints a warning after Markdown and HTML are written. |
| MED-02 | MEDIUM | DONE | Version lives in `version.py` and is read by setuptools. Classifiers, keywords, and project URLs are set. The publish job lists archive members and scans them. |
| MED-03 | MEDIUM | DONE | Markdown escapes gap title, why, and suggestion. HTML already escaped. |
| MED-04 | MEDIUM | DONE | `analysis.json` must match this version, must contain the analysis keys, and must be at most 100_000_000 bytes (raised from 20_000_000 once a 20_000-function static run measured 23 MB compact). A symlinked file that resolves outside the root is not indexed. |
| MED-05 | MEDIUM | DONE | A `pyproject.toml` with any Python file wins the language. `package.json` selects JS or TS only when those files are not outnumbered. `scripts.test` is the JS command when it is a plain argv. Coverage pairing requires one directory-bounded suffix. Nested trees are named, not scored. See RUN-02. |
| RUN-01 | CRITICAL | DONE | Walk prunes `node_modules`, `.git`, `.next`, and other skip dirs before descending. Stops at 20_000 files and records a partial-report note. |
| RUN-02 | HIGH | DONE | Nested manifests are listed on `skipped_projects`, in the report notes, and as a gap. A root run still does not score those trees; run each directory. |
| RUN-03 | HIGH | DONE | `@/` is not a POSIX path, so alias imports survive scrub. `@/` imports count as local for DAR, same as `./`. |
| RUN-04 | MEDIUM | DONE | Missing runner suggestions say `add a test`, not `add a the project test runner test`. A named runner still says `a pytest test`. |
| PYPI-01 | HIGH | DONE | `README.md` is the long description. It states the static default, `--dynamic`, `--deep`, and that a missing Typst binary does not fail the command. |
| PYPI-02 | HIGH | DONE | `docs/security.md` matches the opt-in, the env allowlist, out-of-process probes, scrubbing, and the LLM cap. |
| PYPI-03 | MEDIUM | DONE | The rubric says temp copy, not sandbox. The README embeds that text. |
| PYPI-04 | HIGH | TODO | Trusted publisher for project `coderecoverage` (`recoverage` is taken), workflow `python-publish.yml`, environment `pypi` is pending on PyPI. `ci.yml` has not been observed on GitHub. Tagging is `.github/workflows/release.yml` (Actions → Release). Steps are in `docs/pypi.md`. |
| PYPI-05 | CRITICAL | DONE | The README opens with trusted trees, static default, `--dynamic` as the user, no OS sandbox. Residual: no container. |
| SEC-01 | HIGH | DONE | `assure.py` and `mutate.py` used `shutil.copytree` with default `symlinks=False`. A link inside the checkout pointing at `~/.ssh` or `/etc` was dereferenced into the temp copy and then a test suite ran next to it. `.git`, `node_modules`, `.venv` were copied too. `proc.temp_copy` now copies links as links and skips VCS, dependency, and cache directories. |
| SEC-02 | MEDIUM | DONE | `recoverage-cov-*` and `recoverage-js-cov-*` temp directories were never removed. A `.coverage` SQLite file with absolute paths of the project outlived every run under `%TEMP%`. Both adapters now `rmtree` in `finally`. |
| SEC-03 | MEDIUM | DONE | Discovery capped file count, not bytes. 20_000 files at the 1 MB per-file limit is 20 GB of reads. `MAX_WALK_BYTES` is 200 MB and the partial-report note names both limits. |
| SEC-04 | LOW | DONE | `mcp_api` reported `serverInfo.version` as a hard-coded `0.1.0`. It now reads `recoverage.version.__version__`, the same source the wheel uses. |
| SEC-05 | LOW | DONE | `python_cov.py` still built a `tail` of test stdout and stderr and then `del`'d it. Dead code, but it was the HIGH-01 leak path and it is gone. |
| SEC-06 | LOW | TODO | `SourceCache` holds decoded source in memory, bounded at 64 MB LRU, and is cleared at the end of `run_analysis`. A library caller that raises mid-run keeps that memory until the frame is collected. Not a leak, a ceiling. |
| PERF-01 | HIGH | DONE | `graph._resolve` scanned every known qualname per call edge: O(E·V). A suffix index built once makes it O(E). `query_context` walked all entities and all edges per query: O(V+E). `CodeGraph.__post_init__` builds `_by_qualname`, `_by_symbol`, `_adjacent`, so a query is O(deg). |
| PERF-02 | HIGH | DONE | Every phase re-read every file: `analyze_project`, `attach_sources`, `_assertions`, `_authenticity`, `_firi`, `_test_corpus`, `prompt_coverage`. Five to seven full passes over the tree. `sources.SourceCache` reads once, parses once, and is shared through `pipeline.run_analysis`. |
| PERF-03 | HIGH | DONE | `gaps._function_gap` ran a compiled regex over the concatenated test corpus once per public function: O(F·T). The corpus is tokenised once into a `frozenset`; each lookup is O(1). |
| PERF-04 | HIGH | DONE | `mapcov.match_coverage` compared every structure path against every coverage key: O(S·F). `CoverageIndex` buckets by basename, so a lookup is O(k) for k same-name files. Executed and missing line sets were rebuilt per function; they are built once per file. |
| PERF-05 | MEDIUM | DONE | `structure._analyze_js` and `_analyze_generic` computed `text[:start].count("\n")` per regex match: O(n²) in file size. Newline offsets are collected once and bisected: O(n + m log n). `_python_functions` is iterative, no recursion limit on deep modules. |
| PERF-06 | MEDIUM | DONE | `audit._symbol_defined` re-parsed the target module for every `from x import y`, and `_module_file` stat'd up to four candidate paths per import. `_Resolver` memoises both per run. Test files were parsed three times (assertions, imports, FIRI); they are parsed once via the cache. |
| PERF-07 | MEDIUM | DONE | `blast._walk` rebuilt an edge scan per hop and per node. It builds one undirected adjacency and runs a two-hop BFS: O(V+E). The no-diff whole-graph `radius` was serialised as a sorted list of every symbol, redundant with `graph.entities`. It is now `[]` with `radius_size` alongside. |
| PERF-08 | MEDIUM | DONE | PageRank ran a fixed 40 iterations and redistributed dangling mass per node. Dangling mass is one scalar per iteration and the loop breaks when the L1 delta is under 1e-9. |
| PERF-09 | MEDIUM | DONE | `discover._walk` called `stat()` on every file, including images, lockfiles, and binaries, before checking the suffix. Suffix is checked first; only candidate source files touch the filesystem. |
| PERF-10 | LOW | DONE | `entropy.prompt_coverage` joined all specs and all tests into two strings, tokenised them into lists, then built a `Counter`. It streams tokens into counters directly and the residual is a filtered `Counter`. A dead loop over `source_files` that did nothing is removed. |
| PERF-11 | LOW | DONE | `pbt._targets` read and scanned the file for every function before slicing to four. `sbst.search` read and parsed the file once per function. Both memoise per file; `_targets` stops at the limit. |
| PERF-12 | LOW | DONE | `graph._calls` used list membership for dedupe, O(k²) per function body, and recursed. It is an iterative stack with a `set`. Builtin filter is a module-level `frozenset`. |
| PERF-13 | MEDIUM | TODO | `structure` parses every Python file with `ast` and `graph.index_project` parses the same file again with Tree-sitter. Two full parses per file. Merging them needs one intermediate representation both consumers accept. Not started. |
| PERF-14 | LOW | TODO | `graph._louvain` is the naive local-move loop with a Python dict per community. It is fine at the sizes discovery allows (20_000 files) and would be the next hot spot on a monorepo that lifted that cap. Not started. |

## Sahaay run

Command was `recoverage run` with output outside `E:\Sahaay`. Nothing in that repo was edited. `--dynamic` was not used, so Sahaay's tests were not executed.

| Target | Result |
| --- | --- |
| `E:\Sahaay` | No report. Still running after 7.5 minutes, about 460s of CPU, 73MB RSS, zero files in the output directory. Killed. |
| `E:\Sahaay\packages\theme` | Finished in about 14s. MRS 0, gate `blocked`, no runner, TypeScript, two functions. |
| `E:\Sahaay\apps\web` | Finished in about 15s. MRS 0, gate `blocked`, 24 gaps (1 critical, 13 high, 10 medium). `package.json` has no test script, so "no runner" is fair for that package. |

RUN-01 through RUN-04 are fixed in this tree. The root row above is the pre-fix hang. A later `recoverage run E:\Sahaay --no-llm` finished: score 0.0, gate `blocked`, 13 gaps, and the report names `frontend`, `apps/web`, `firebase/functions`, `packages/api-client`, and `packages/theme` as skipped. The first of those runs labeled the root `javascript` because one `.js` file lost to `package.json` despite three Python scripts. That override now requires the JS/TS files to be at least as numerous. A missing Typst binary also deletes a leftover `report.pdf` so the summary does not point at a stale PDF. Nothing under `E:\Sahaay` was written.

MEDIUM rows are done. The narratives under "Release-blocking findings" describe the original bugs. Where they disagree with this scoreboard, the scoreboard is the status. GitHub Actions has not been observed.

### After the performance pass

Static `run --no-llm` on the same two targets, same machine, this tree: root `E:\Sahaay` 1.9s, `apps/web` 2.1s, identical scores, gate, and gap counts to the previous run. The committed `HEAD` (before this session's RUN-01 fix) was killed on the root at 388s with no output and took 2.5s on `apps/web`. Small trees are dominated by interpreter start and the matplotlib import, so the asymptotic work was measured on a synthetic tree instead: 2_000 modules, 20_000 functions, 200 test files, static, `cProfile` on `run_analysis`. Before this pass 67.3s and 134M function calls; after it 24.4s and 49M. The top remaining costs are `ast.parse` itself, the Tree-sitter walk in `graph._walk_file` (PERF-13), and `json.dumps` of a 23 MB payload.

## Verdict

The bug scoreboard is closed. PYPI-01, PYPI-02, PYPI-03, and PYPI-05 are done. PYPI-04 is the remaining upload step: create the trusted publisher, then cut a GitHub Release. `--dynamic` still has no OS container. The project page says so.

SEC-01 through SEC-05 and PERF-01 through PERF-12 are in this tree and covered by the suite. SEC-06, PERF-13, and PERF-14 are open and none of them blocks upload.

The sections under "Release-blocking findings" are the original review. They are not the status. Where they disagree with the scoreboard, the scoreboard wins.

The `src` layout and the explicit package-data list are still sound. A fresh pattern scan was not repeated this revision. The checked-in sample no longer contains `/agent/recoverage/examples/fixture`. A new run scrubs absolute paths to a basename before write.

## Release-blocking findings

### CRIT-01 — Project code runs with the caller's authority

**Priority: CRITICAL. Status: TODO.**

`run_analysis` still invokes coverage, property trials, mutation, timing, and SBST on every run (`src/recoverage/pipeline.py`). Python and JavaScript tests are subprocesses. PBT, SBST, and timing import the project and call functions in this process. Import-time code runs first.

`_BANNED` is a substring list. It is not a security control. `assure.py` and `mutate.py` copy the tree to a temp directory and then run it. That copy is what the rubric calls a sandbox. It is not one.

Python coverage copies `os.environ` and deletes only `RECOVERAGE_LLM_API_KEY` (`src/recoverage/adapters/python_cov.py`). Mutation and draft subprocesses copy the environment and do not delete the key. In-process calls see the process environment and the filesystem.

**Impact:** An untrusted checkout can read credentials, write files the user can write, spawn processes, use the network, or hang the machine. CI with secrets loaded makes this worse. Documenting "trusted only" does not change the code path.

**Required changes:** unchanged from the first review. Static-only default. Real isolation or a hard refusal. Environment allowlist. Process-tree kill. Probes out of process. Symlink-checked snapshot that drops `.git`, `.env*`, keys, and caches.

### CRIT-02 — Source constants are persisted and can be committed

**Priority: CRITICAL. Status: TODO.**

`_held_constants` still collects string and numeric constants compared with a parameter (`src/recoverage/sbst.py`). Those values are still `best_args`, still serialized in `analysis.json`, and still rendered with `repr` in `src/recoverage/drafts.py`. `assure.py` can copy that file into the project. `tests/test_prd_engines.py` still requires `BEARER_ADMIN_TOKEN` to show up in the case. That test is a demonstration of the bug, not a regression that forbids it.

**Impact:** A literal credential in source can land in JSON, Markdown previews, CI artifacts, and a test the user commits. `.gitignore` does not see inside `analysis.json`.

**Required changes:** unchanged. Do not persist raw arguments. Scrub before write, fail closed on high-confidence patterns. No silent copy-back. Tests that prove the fake secrets are absent from every output.

### CRIT-03 — A failing test run and the gate

**Priority: CRITICAL. Status: IN PROGRESS. Not done.**

What landed: `decide_gate` returns `blocked` when coverage was measured and `tests_exit_code` is not `None` and not `0` (`src/recoverage/score.py`). The sentence includes `the test run exited N`. `tests/test_score.py` checks that a named `merge-ready` or `production-ready` threshold fails, and that exit 0 can still be `production-ready`.

What did not land, and why this stays open:

- `tests_exit_code is None` is treated as success. The condition is `not in (None, 0)`. A measured result with a missing exit code does not block. Fail-closed would treat `None` as unknown and block.
- `meets_threshold` for a number compares MRS only (`return result.score >= float(threshold)`). `--threshold 70` exits 0 when the suite exited 1, as long as the score is high enough. The original bug was "CI can go green while tests are red." The numeric form of that bug is still there. The example workflow uses a gate name, so that one file is safe. The CLI help still offers a number.
- A coverage timeout returns `unmeasured` and leaves `tests_exit_code` unset (`python_cov.py` on `TimeoutExpired`). That cannot be `merge-ready`, because unmeasured coverage cannot. It is also not recorded as a failed test run. The report can say coverage was not measured, which is the wrong reason.
- Runner detected, runner started, and tests passed are still one blended `measured` flag plus an exit code. The original required those as separate facts.

**Do not mark CRIT-03 DONE until a red suite fails every threshold form, including a number, and a missing exit code cannot be `production-ready`.**

### CRIT-04 — Network use

**Priority: HIGH. Status: IN PROGRESS. Not done.**

What landed:

- The CLI passes `off` unless `--llm` (`src/recoverage/cli.py`, `_llm_mode`). A key in the environment does not create a client. Pipeline defaults are `off`.
- `client_from_env` rejects a non-`https` base URL unless the host is `localhost`, `127.0.0.1`, or `::1`.
- SBST catches a failed `complete` and falls through to AST constants (`sbst.py`, `_seed`).

What did not land:

- `llm_mode="auto"` still builds a client whenever the key is set. Any library caller who passes `auto`, or who has not moved off an old call site, gets the original bug. The CLI does not pass `auto`. The function still implements it.
- `--llm` still sends gap id, title, why, file, symbol, and suggestion, and SBST still sends the symbol and parameter names. Paths are not redacted. There is no preview step.
- `urlopen` reads the body with no limit (`llm.py`). Redirects are not inspected before the `Authorization` header is attached.
- Scheme check is not a host allowlist. `https://evil.example` is accepted if the user set `RECOVERAGE_LLM_BASE_URL`.

**Impact that remains:** opt-in network can still leak internal paths and can still hand the API key to a URL the environment names. A hostile or huge response can still be read into memory. An optional SBST network error no longer aborts the run. Gap enrichment already caught its own errors.

## High findings

### HIGH-01 — Artifacts hold sensitive project metadata

**Priority: HIGH. Status: TODO.**

`analysis.json` still dumps absolute `root` and `import_root`, signatures, docstrings, the coverage argv, fuzz arguments, and coverage notes. Python notes still include the tail of test stdout and stderr when the suite fails. Markdown still prints `project.root`. The example workflow still uploads `analysis.json`.

The committed sample's `/agent/recoverage/...` strings were rewritten to project-relative paths in `analysis.json` and `report.md`. That is a cleanup of one artifact. `report.pdf` was not regenerated. The writer in `pipeline.py` was not changed. The next `recoverage run` puts the machine path back.

### HIGH-02 — No per-call deadline, no run budget

**Priority: HIGH. Status: TODO.**

Subprocess coverage and pytest calls have timeouts. `time_functions`, SBST `_trace`, and PBT `_check` call the target directly. Discovery skips files over 1_000_000 bytes and has no file-count or total-byte cap. `run_analysis` always runs every expensive phase. Mutation allows 120s per suite. Draft assurance can run five suites, three attempts, plus coverage and mutant checks.

### HIGH-03 — Exceptions can fill the property score

**Priority: HIGH. Status: TODO.**

`pbt.py` returns success for `TypeError`, `ValueError`, `KeyError`, and `OverflowError` in structural, determinism, and substitution checks. `score.py` turns `passed / trials` into up to 25 points. The fixture's own sample report shows 1000/1000 passed, including `charge` and `refund`, which the coverage section says never ran. That is the score awarding resilience for calls that did not establish the property.

### HIGH-04 — Timing can be a perfect score with no measurement

**Priority: HIGH. Status: TODO.**

`time_functions` returns `ran: True` after it has a candidate list, including when every import fails and `loaded` is empty, and when every timed call throws (those calls `continue`). `_timing` awards 10 whenever `ran` is true and `regression` is false. The comparison is two input sizes on one revision. The docs say so. The points are still real MRS points.

### HIGH-05 — Deep analysis is unconditional

**Priority: HIGH. Status: TODO.**

No flag skips PBT, mutation, timing, or SBST. PageRank still redistributes each dangling node by iterating every node, 40 times (`graph.py`). Discovery materializes the full file list first.

### HIGH-06 — Host interpreter state

**Priority: HIGH. Status: TODO.**

PBT, SBST, and perf insert `sys.path`, set `sys.dont_write_bytecode`, and may pop `sys.modules`. SBST installs a trace hook for the call and restores the previous one in `finally` on the trace path. `_DEPTH` in `pipeline.py` is a global integer. Two threads can both pass it. This library is not safe inside an IDE, a notebook, or a service.

### HIGH-07 — Stale coverage files

**Priority: HIGH. Status: TODO.**

Python writes `output_dir / ".coverage"` and `coverage.json` without deleting them first. JavaScript reuses `js-coverage/` and will accept the first JSON it finds.

### HIGH-08 — Release workflow does not test the artifact

**Priority: HIGH. Status: TODO.**

`python-publish.yml` is unchanged: floating `3.x`, `pip install build`, upload, publish. Actions are `@v4`, `@v5`, `@release/v1`. OIDC scoped to the publish job is necessary and not sufficient. `ci.yml` runs `twine check` on a pull request build. That is a different job from the one that publishes, and it does not install the wheel or smoke the CLI. HIGH-09 being done does not close this.

### HIGH-09 — CI targets

**Priority: HIGH. Status: DONE.**

`.github/workflows/pylint.yml` (Python 3.8–3.10, pylint only) is gone. `ci.yml` runs pytest on 3.11, 3.12, and 3.13 with Typst installed, and a second job runs `python -m build` and `twine check`. This was not watched on GitHub. Action refs are still tags. That leftover is HIGH-08, not a reason to reopen the matrix bug.

## Medium findings

All TODO. None of them are the reason the PyPI answer is no. They are the reason a first release would be a support problem even after the ship list is done.

### MED-01 — Install is heavier than the core

**Priority: MEDIUM. Status: TODO.**

`coverage`, `matplotlib`, `hypothesis`, and three Tree-sitter packages are hard dependencies. Typst is an external binary. `write_typst_pdf` still raises when it is missing, after Markdown and HTML have been written, so the CLI exits 2. There is no `--no-pdf`.

### MED-02 — Metadata

**Priority: MEDIUM. Status: TODO.**

`pyproject.toml` and `src/recoverage/version.py` both say `0.1.0`. Classifiers, keywords, and project URLs are absent. Nobody has listed the sdist and wheel members from a built archive in this review.

### MED-03 — Markdown is raw

**Priority: MEDIUM. Status: TODO.**

`html_report.py` escapes. `report.py` interpolates `why`, `suggestion`, and paths into Markdown. LLM text and repository names can carry links or remote images. Hosting `report.md` is a content problem.

### MED-04 — JSON and paths

**Priority: MEDIUM. Status: TODO.**

`analysis_from_dict` splats dicts into dataclasses. No version field check, no size cap. The walk does not refuse a symlink that leaves the root. `show` binds `127.0.0.1` only, which is the right bind, and still serves whatever the report contains to any local process.

### MED-05 — Detection guesses

**Priority: MEDIUM. Status: TODO.**

Primary language is the extension with the most files. Packages are direct `*/__init__.py` children. The JS adapter runs a hard-coded jest or vitest command, not `scripts.test`. Coverage file matching falls back to suffix equality.

## What is actually in good shape

These are not mitigation for the ship list.

- Source lives under `src/`. Package data is an allowlist: `py.typed`, `RUBRIC.md`, `templates/report.typ`.
- The CLI default no longer opens a socket. Child commands are argv arrays, not a shell string. HTML is escaped. `show` binds loopback.
- The gate sentence does not invent a missing runner, and a measured nonzero exit is now one of the reasons it can state.
- The README embeds the rubric. That rubric says temp copy. `docs/security.md` matches the static default and the `--dynamic` opt-in.
- Publish uses PyPI trusted publishing, and `id-token: write` is only on the publish job.

## Minimum bar, restated

The bug scoreboard is DONE. Upload when PYPI-04 is done: trusted publisher, green `ci.yml`, GitHub Release, no laptop wheel. The project page already states the isolation limit.
