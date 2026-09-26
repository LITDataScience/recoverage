# Pipeline

`run_analysis` in `src/recoverage/pipeline.py` always discovers, parses, maps gaps, builds the call graph, and scores. Coverage runs only with `--dynamic`. Property trials, mutation, timing, and search run only with `--deep` (which implies `--dynamic`). There is no separate flag per engine.

```mermaid
flowchart LR
  discover[discover.py] --> structure[structure.py]
  structure --> coverage[adapters]
  coverage --> mapcov[mapcov.py]
  mapcov --> gaps[gaps.py]
  gaps --> llm[llm.enrich_gaps]
  discover --> graph[graph.py]
  mapcov --> engines[pbt mutate perf sbst blast entropy audit]
  graph --> engines
  engines --> score[score.py]
  score --> outputs[Markdown HTML PDF analysis.json]
  outputs --> generate[drafts.py plus assure.py]
```

`generate` is a separate command. It reuses `analysis.json` when that file is already in the output directory.

## Module map

| Module | Role |
| --- | --- |
| `host.py` | CPU, RAM, and free temp space. Scales the walk, the cache, the run budget, and the parse pool. |
| `cli.py` | argparse. Exit codes. LLM mode. Docs URL. |
| `pipeline.py` | Orders the phases, writes `analysis.json`, `execute_run` / `execute_report` / `execute_generate`. |
| `reportview.py` | One projection of `Analysis` shared by Markdown, HTML, and the PDF. |
| `svgcharts.py` | Gauge and bar charts as SVG. No matplotlib. |
| `discover.py` | Walks the tree. Language, runner, packages, flake markers. Suffix check before `stat`. The cap is 20_000 files or 200 MB on an 8 GB machine, and `host.py` scales it. |
| `sources.py` | `SourceCache`: one read and one `ast.parse` per file per run, 64 MB LRU, shared by structure, gaps, audit, and entropy. |
| `structure.py` | Functions, branches, cyclomatic complexity, heuristic risk tags. Statement-skeleton walks; one pass per function body. |
| `adapters/python_cov.py` | `coverage run --branch`, then `coverage json`. |
| `adapters/javascript_cov.py` | `npx --no-install` `c8` or `nyc`. Parses Istanbul JSON. |
| `adapters/static.py` | `measured=False` when nothing ran. |
| `mapcov.py` | Joins statement hits onto functions via `CoverageIndex` (exact path, then basename bucket). Package stats. Hotspots. |
| `gaps.py` | Untested functions, partial branches, missing direct tests, no runner, flake markers, parse errors. Test corpus is one identifier set. |
| `graph.py` | Tree-sitter entities, call edges resolved through a suffix index, PageRank with convergence stop, Louvain. `CodeGraph` carries symbol and adjacency indexes for O(deg) queries. |
| `entropy.py` | Lexical ΔH over spec tokens vs test tokens. |
| `blast.py` | Union coverage of a 2-hop call-graph radius. |
| `pbt.py` | Property trials through `probe_worker`. Covered functions in the project packages are chosen first. A function that raises on every call is left out of the score. |
| `sbst.py` | Search for arguments through `probe_worker`. Feeds drafts. |
| `proc.py` | Child env allowlist, process-tree kill, `temp_copy` (symlinks kept as links, VCS and dependency dirs skipped). |
| `mutate.py` | Operator flip on a temp copy. Up to 5 functions. |
| `perf.py` | Mann-Whitney on this revision. |
| `audit.py` | CRAP, assertion strength, dependency authenticity, static flake risk. Outside MRS. |
| `score.py` | Weighted MRS and the gate. Reads `RUBRIC.md` at import. |
| `llm.py` | Optional OpenAI-compatible chat client. |
| `report.py` | Markdown. |
| `html_report.py` | Single-file dashboard. Inline SVG, escaped text, CSP hashes. |
| `charts.py` | Three matplotlib PNGs, written only when matplotlib imports. |
| `typst_render.py` | `mrs.json` + `templates/report.typ` → PDF. Missing Typst warns and exits 0. |
| `drafts.py` | Plain pytest from SBST cases and a fixed `_CASES` property sample. No Hypothesis import. |
| `assure.py` | Temp copy, compile, five runs, coverage-or-kill filter, copy back. |
| `generate.py` | `PlannedTest` record. |
| `display.py` | Loopback server for `show`. |
| `mcp_api.py` | In-process JSON-RPC over `CodeGraph`. No socket. |
| `models.py` | Dataclasses and `analysis.json` (de)serialization. |
| `version.py` | `__version__`. `pyproject.toml` reads it. It is not copied there. |

## Discovery

`discover` prunes `.git`, virtualenvs, `node_modules`, `.next`, caches, `dist`, `build`, `recoverage-out`, `sample-report`, and any directory whose name starts with `.` before descending. A directory that contains its own `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, or `pom.xml` is recorded on `skipped_projects` and not walked. Files over 1_000_000 bytes are skipped. The walk stops at the host budget (20_000 files or 200 MB on an 8 GB machine) and says the report is partial.

Primary language is the source extension with the most files. A `pyproject.toml` with any Python file selects Python. A `package.json` and no `pyproject.toml` selects TypeScript or JavaScript only when those files are at least as numerous as every other language. Python packages are the immediate children of `src/` that contain `__init__.py`, or of the project root when that layout is absent. Namespace packages and deeper layouts are not detected.

Python runner: pytest if `pyproject.toml` has `[tool.pytest]`, or `pytest.ini`, `conftest.py`, or `setup.cfg` mentions pytest. Otherwise a sample of test files is scanned for `unittest`. JavaScript/TypeScript: vitest if the config or dependency or `scripts.test` says so, else jest when a config, dependency, or test files exist.

Python coverage tool is always reported as `coverage.py`. JS coverage tool is `c8` or `istanbul` only when the binary is under `node_modules/.bin` or the name is in `package.json`.

## Coverage

Python: `coverage run --branch --source=<packages>`, then pytest (or `unittest discover`). Timeout 180s. Pytest `addopts` are cleared and `-p no:cov` is set, because a project `--cov` flag under `coverage run` makes pytest exit 4 when pytest-cov is not installed. Unimported Python modules are counted as uncovered in the project percentage, and the raw tool percentage is printed beside it. JavaScript files stay unmeasured in that run; they are not given a coverage of 0. With `--branch`, coverage.py's `percent_covered` blends arcs into statements, so the score uses statement coverage (`covered_lines / num_statements`), not that headline.

A nonzero pytest exit still returns `measured=True` when `coverage.json` was written, except exit 4. Exit 4 means pytest never ran the suite: either it rejected the command, or it could not import `conftest.py` because this interpreter does not have the project's dependencies. Coverage stays unmeasured and the note names the missing module. The gate then blocks. See [scoring.md](scoring.md). Test stdout and stderr tails are not stored. Run `recoverage` with the project's own Python when that environment is not the one Recoverage is installed in.

JS: `package.json` `scripts.test` when it is a plain argv (`vitest`, `jest`, `npm`, `pnpm`, `yarn`, `npx`, `node`, `turbo`). Shell pipelines are ignored and the fallback is `npx --no-install vitest run` or `jest --runInBand`, wrapped in `c8` or `nyc`. Timeout 180s.

Other languages, or a tree with no runner, get the static adapter: `line_percent` is `None`, not `0`.

File matching is exact, or the single coverage key that shares a directory-bounded suffix. Two files named `pay.py` in different directories are not joined.

## Structure and risk

Python uses `ast`. Risk is a name list (`charge`, `auth`, `password`, …) plus body patterns (`eval`, `subprocess`, `shell=True`, …) plus a bump when complexity is at least 8. JavaScript and TypeScript function extraction is a regex, not the Tree-sitter grammar. The Tree-sitter JavaScript grammar is used only by the call graph. Other languages get a generic `func`/`fn`/`def` scan with no branches.

## Gaps

Sorted critical → low, then id `G01`…. Kinds: `no-test-runner`, `flake-marker`, `unmeasured-function`, `untested-function`, `partial-branch`, `missing-critical-path-test`, `parse-error`, `llm-error`. A public function at 0% coverage with risk ≥ 0.7 is `critical`. That is a heuristic, not a proof the lines are untested when coverage was not measured.

## Graph query

`mcp_api.handle` speaks one JSON-RPC request (`initialize`, `tools/list`, `tools/call`) and returns one response. Tools are `query_context`, `pagerank`, and `communities`. It does not open a socket and it is not a running MCP server. `query_context` returns the focal symbol's signature, docstring, byte range, PageRank, community, and up to 8 neighbors.
