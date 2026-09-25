# CLI

```bash
recoverage run [path] [--output DIR] [--dynamic] [--deep] [--threshold GATE|SCORE] [--llm | --no-llm]
recoverage report [path] [--output DIR] [--input analysis.json] [--dynamic] [--deep] [--threshold GATE|SCORE] [--llm | --no-llm]
recoverage generate [path] [--output DIR] [--dry-run] [--dynamic] [--deep] [--llm | --no-llm]
recoverage show [path] [--output DIR] [--port N] [--no-open]
```

`path` defaults to the current directory. `--output` defaults to `<project>/recoverage-out`.

## Commands

`run` discovers the project and writes the reports in [reports.md](reports.md). Without `--dynamic` it does not import the project or start a test runner. `--dynamic` runs the tests and prints that there is no OS sandbox. `--deep` implies `--dynamic` and also runs property, mutation, timing, and search probes out of process.

`report` re-renders Markdown, HTML, and PDF from `analysis.json` when that file is already in the output directory, or from `--input`. If the file is missing, `report` analyzes first. Re-rendering does not re-check that the JSON matches the current schema.

`generate` writes new test files. It does not delete anything and it does not overwrite an existing file; a numeric suffix is used instead. `--dry-run` writes nothing in the project and leaves `generation-preview.md` plus `generation-manifest.json` in the output directory. See [test-generation.md](test-generation.md).

`show` looks for `report.html` at the path you pass, then `<path>/recoverage-out/report.html`. `--output` points at a report directory that is neither of those. `--port 0` picks a free port. If the file is missing, `show` exits `2` and does not run an analysis. The server binds to `127.0.0.1` and serves only `/` and `/report.html`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Finished. With no `--threshold`, a low score still exits 0. |
| 1 | `--threshold` was missed. |
| 2 | Usage or setup error: missing project, missing `report.html` for `show`, both `--llm` and `--no-llm`, missing API key with `--llm`, a non-HTTPS LLM URL, Typst compile failure, or a nested `execute_*` call in the same process. A missing Typst binary does not use this code. |

`--threshold` accepts a gate name or a number. Gate rank is `blocked` < `needs-review` < `merge-ready` < `production-ready`. A numeric threshold fails when the test run failed, even if MRS is high enough. Gate rules are in [scoring.md](scoring.md).

## LLM

The default is offline. A `RECOVERAGE_LLM_API_KEY` in the environment does not open a socket. `--llm` opts in. `--no-llm` is the same as the default. Passing both exits `2`.

`--llm` requires the key. The client is `urllib`, not a vendor SDK. On a run it sends, for up to 20 gaps: `id`, `severity`, `kind`, `title`, `why`, `file`, `symbol`, `suggestion`. Search-based testing, on a coverage stall, sends the symbol and parameter names. Whole source files are not uploaded. If gap enrichment fails, the heuristic text stays and a finding records the failure. If the stall call fails, search falls back to AST constants.

| Variable | Purpose |
| --- | --- |
| `RECOVERAGE_LLM_API_KEY` | Required when `--llm` is passed. |
| `RECOVERAGE_LLM_BASE_URL` | OpenAI-compatible base. Default `https://api.openai.com/v1`. Must be `https`, except `http` on `localhost`, `127.0.0.1`, or `::1`. |
| `RECOVERAGE_LLM_MODEL` | Default `gpt-4o-mini`. |

Library `llm_mode` `"off"` and `"auto"` stay offline. Only `"on"` builds a client. The CLI passes `"on"` only when `--llm` is set.

## Library

```python
from recoverage import execute_run, execute_report, execute_generate

analysis, code = execute_run(path, output, llm_mode="off", threshold="merge-ready")
```

`llm_mode` defaults to `"off"`. `dynamic` and `deep` default to false. One `execute_run` / `execute_report` / `execute_generate` at a time per process. A nested or overlapping call raises `RuntimeError` (`recoverage is already running in this process`). Probes do not insert `sys.path` in this process. See [security.md](security.md).
