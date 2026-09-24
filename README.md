# Recoverage

Recoverage measures a project, maps the gaps onto functions, and scores whether the suite is ready to merge. It discovers the language and test runner, runs coverage when a tool is already installed, and writes one analysis as Markdown, a self-contained HTML file, and a PDF.

It can also draft tests in the project's own runner. Drafts are new files. Existing tests are never overwritten or deleted.

Offline by default. An OpenAI-compatible chat API is used only when `RECOVERAGE_LLM_API_KEY` is set and you do not pass `--no-llm`.

The design name in the original spec is OmniCov-AI. The package and the CLI are `recoverage`.

## Install

Python 3.11+. This package is not on PyPI. Install it from a checkout of this repo.

```bash
git clone https://github.com/LITDataScience/recoverage.git
cd recoverage
python3 -m pip install -e ".[dev]"
```

`".[dev]"` adds pytest so you can run Recoverage's own tests. For the CLI alone, `python3 -m pip install -e .` is enough.

After that, `recoverage` works when your environment exposes installed scripts. `python3 -m recoverage` always works from the checkout.

Runtime dependencies: `coverage`, `matplotlib`, `hypothesis`, `tree-sitter`, `tree-sitter-python`, `tree-sitter-javascript`.

PDF compilation needs the [Typst](https://github.com/typst/typst) CLI (`typst`) on your `PATH`. Without it, Markdown and HTML still write, and PDF compilation raises.

JavaScript measurement shells out to a local `c8` or `nyc` via `npx --no-install`. Recoverage does not install npm packages.

## Try the fixture

`examples/fixture` is a small `shop` package. `tests/test_cart.py` covers one happy path. Payments and pricing are untested. `examples/sample-report/` is a real run of that fixture (MRS 32.5, gate `blocked`, statement coverage 16.7%).

```bash
python3 -m recoverage run examples/fixture --output examples/sample-report --no-llm
python3 -m recoverage show examples/sample-report
```

`show` serves the `report.html` that `run` already wrote. It does not analyze again. Open `examples/sample-report/report.html` directly if you do not want a local server. `--no-open` skips the browser.

Own tests:

```bash
python3 -m pytest
```

## CLI

```bash
recoverage run [path] [--output DIR] [--threshold GATE|SCORE] [--llm | --no-llm]
recoverage report [path] [--output DIR] [--input analysis.json] [--threshold GATE|SCORE] [--llm | --no-llm]
recoverage generate [path] [--output DIR] [--dry-run] [--llm | --no-llm]
recoverage show [path] [--output DIR] [--port N] [--no-open]
```

`run` discovers the project, measures coverage, scores, and writes the reports below. Default output directory is `<project>/recoverage-out`. Default LLM mode is on only when `RECOVERAGE_LLM_API_KEY` is set. `--llm` requires the key. `--no-llm` forbids the network.

Exit code is `1` when `--threshold` is missed, `2` on usage or setup errors, `0` otherwise. With no threshold, a low score still exits `0`.

`report` re-renders Markdown, HTML, and PDF from `analysis.json` when that file is already in the output directory. If it is missing, `report` analyzes first.

`generate` writes new test files. It does not delete anything and it does not overwrite an existing file; a numeric suffix is used instead. `--dry-run` writes nothing in the project and leaves a preview in the output directory.

`show` looks for `report.html` at the path you pass, then `<path>/recoverage-out/report.html`. `--output` points at a report directory that is neither of those. `--port 0` picks a free port. If the file is missing, `show` exits `2` and does not run an analysis.

Library:

```python
from recoverage import execute_run

analysis, code = execute_run(path, output, llm_mode="off", threshold="merge-ready")
```

## Reports

`run` and `report` write these from the same analysis:

| File | What it is |
| --- | --- |
| `report.md` | Score, gate sentence, coverage, findings, suggestions, charts as PNG links, rubric. |
| `report.html` | Same content in one file. Inline CSS. Charts are `data:image/png;base64` URIs. Opens with no server. |
| `report.pdf` | Typst render of `mrs.json`. Vector bars, not a screenshot of the HTML. |
| `charts/*.png` | Matplotlib images used by the Markdown. |
| `analysis.json` | The analysis `report` can re-render. |
| `coverage.json` | coverage.py output, when that adapter ran. |
| `mrs.json` | Numbers the PDF template reads, including the gate sentence. |

The gate sentence names only the causes that fired. A project whose pytest run exited 0 is not described as having no test runner. The rubric table still defines the full blocked rule.

## What a run does

1. Walk the tree. Infer language, test runner (pytest, unittest, jest, vitest), existing tests, entry points, and packages. A nested directory with its own manifest is a separate project.
2. Parse structure. Python uses `ast` plus a Tree-sitter index (byte range, line range, call edges). JavaScript and TypeScript use the Tree-sitter JavaScript grammar. Other languages get a generic function scan. Risk tags are heuristic (names like `charge` / `auth`, plus calls like `eval` and `subprocess`).
3. Run coverage when a tool exists. Python: `coverage.py --branch`. JS/TS: `c8` if it is present, otherwise `nyc`/`istanbul`. If neither JS tool is installed, or the language has no adapter, runtime coverage is not measured and the report says so. Unimported Python modules count as uncovered in the project percentage. The raw tool percentage is printed beside it. With `--branch`, coverage.py's `percent_covered` blends arcs into statements, so the score uses statement coverage.
4. Map hits onto functions. Search-based tests and in-process property trials exercise pure functions. Mutation flips an operator on a temp copy and is reported separately.
5. Build gaps: untested functions, partial branches, missing direct tests for risky code, absent runner, flake markers.
6. Score. See the rubric below.
7. Optionally ask an OpenAI-compatible API to rewrite gap explanations. If the call fails, the heuristic text stays and a finding records the failure.
8. Write Markdown, HTML, and PDF.

`generate` drafts pytest, or jest/vitest-shaped, tests from signatures. It does not lock observed return values. A draft is kept only after it compiles, runs five times, and adds covered lines or kills a mutant the current suite survived. Functions that look like they do I/O are skipped.

## LLM

| Variable | Purpose |
| --- | --- |
| `RECOVERAGE_LLM_API_KEY` | Required for any network call. |
| `RECOVERAGE_LLM_BASE_URL` | OpenAI-compatible base. Default `https://api.openai.com/v1`. |
| `RECOVERAGE_LLM_MODEL` | Default `gpt-4o-mini`. |

No vendor SDK. The client is `urllib`. `--no-llm` never constructs it. Tests in this repo forbid `urlopen`.

## CI

Copy `examples/ci/recoverage.yml` to `.github/workflows/recoverage.yml` on a project you want to gate. The example fails the job when the result is below `--threshold merge-ready`. Change the threshold to `production-ready`, `needs-review`, `blocked`, or a number such as `70`.

Gate rank is `blocked` < `needs-review` < `merge-ready` < `production-ready`.

The workflow's `pip install recoverage` line is for after this package is published. From a checkout of this repo, install with `pip install -e .` instead.

## Recoverage score rubric

The score is the Merge Readiness Score (MRS), 0–100. It is the PRD's weighted sum, not a line-coverage percentage.

| Factor | Points | How it is measured |
| --- | --- | --- |
| Structural coverage | 40 | 60% project statement coverage + 40% branch coverage. Unmeasured runtime coverage scores 0. coverage.py's own `percent_covered` is reported beside it and is not the score: with `--branch` that headline blends arcs into statements. |
| Property-based resilience | 25 | Share of in-process property trials that held. The properties are structural conformance, determinism, and entity substitution. The engine runs at least 1,000 inputs when pure functions exist. Failing inputs are shrunk. This is not a frozen expected-output check. |
| Prompt / semantic alignment | 15 | ΔH, the drop in Shannon entropy of specification tokens once tokens named by tests are removed. Offline this is a lexical spotlight, not transformer attention. No spec text scores 0. |
| Blast radius safety | 10 | Union coverage of the call-graph radius. With no diff, the radius is the whole indexed graph and the report says so. |
| Execution-time efficiency | 10 | Mann-Whitney U between baseline inputs and heavier inputs on this revision. Points are lost only when p < 0.05 and the median is more than 8× slower. This is not a cross-commit benchmark. |

Mutation testing is a separate measurement. When it runs, mutants are applied on a temp copy and the kill count is printed. It is not silently folded into MRS. If it does not run, the report says it did not run.

Flake markers found by a static scan subtract 2 points, floored at 0. That scan is not a reproduction. Drafts that `recoverage generate` keeps are executed 5 times in a sandbox before they are copied back.

### Gates

MRS is mapped onto four gates so a CI job can fail below a named bar. The PRD badge uses the same threshold, default 85.

| Gate | Rule |
| --- | --- |
| blocked | No test runner, or measured project statement coverage is below 20%, or MRS is below 40. Badge: NOT MERGEABLE. |
| needs-review | A runner exists and MRS is at least 40, but the merge bar is not met. Unmeasured runtime coverage cannot be graded above this gate. |
| merge-ready | MRS ≥ 70, statement coverage ≥ 60%, runtime coverage was measured, and there is no critical gap. Badge: MERGEABLE. |
| production-ready | MRS ≥ 85 (the PRD threshold), statement coverage ≥ 60%, runtime coverage was measured, and there is no critical gap. Badge: PRODUCTION READY. |

`--threshold` accepts a gate name or a number. A gate threshold passes only when the result gate ranks at least that high: blocked < needs-review < merge-ready < production-ready. A numeric threshold passes when MRS is greater than or equal to the number.

### Separate from MRS

CRAP, assertion strength, dependency authenticity, static flakiness risk, and the mutation score are reported on an authenticity scorecard. They are not added into the 100 points and they do not move the gate. A generated draft is kept when it adds covered lines or kills a mutant the existing suite left alive. That filter is there because a coverage bump with a vacuous assertion is not evidence. Drafts still do not lock in an observed return value.

## What it does not do

- It does not pretend lexical ΔH is transformer attention. The prompt factor is labeled.
- It does not edit your source to fix a bug it finds. Property failures are reported and shrunk, not patched into the project.
- It does not delete your code or overwrite an existing test file. Drafts are filtered in a temp copy, then new files are copied back.
- It does not freeze observed return values into assertions. Specs come from signatures.
- It does not run a cross-commit performance benchmark. Timing is Mann-Whitney on this revision only.
- It does not cover every language at runtime. Tree-sitter indexes Python and JavaScript. Coverage runtimes are coverage.py, or c8/istanbul when already installed.
- It does not call an LLM unless `RECOVERAGE_LLM_API_KEY` is set and `--no-llm` was not passed. A coverage stall then uses AST constants instead of the API.
- It does not `npm install` coverage tools.
- It does not query PyPI or npm. Dependency authenticity is the workspace, the standard library, and declared manifests.
- It does not report MC/DC or basis-path coverage. Branch coverage is the decision measure it actually runs.
- It does not fold CRAP, assertion strength, or the mutation score into MRS. Those sit on a separate scorecard.
- It is not a security audit. `production-ready` means MRS cleared 85 with measured coverage and no critical gap.
