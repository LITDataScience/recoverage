# Recoverage

Recoverage measures a project, maps the gaps onto functions, and scores whether the suite is ready to merge. It discovers the language and test runner, runs coverage when a tool is already installed, and writes one analysis as Markdown, a self-contained HTML file, and a PDF.

It can also draft tests in the project's own runner. Drafts are new files. Existing tests are never overwritten or deleted.

Trusted trees only. This is not a scanner for a hostile repository. Default `recoverage run` does not execute project code and does not start a test runner. `--dynamic` and `--deep` run that checkout as you, in a child process, with no OS sandbox. See [docs/security.md](docs/security.md).

The design name in the original spec is OmniCov-AI. The package and the CLI are `recoverage`.

## Install

Python 3.11+.

```bash
python3 -m pip install recoverage
```

Charts and the Tree-sitter call graph need the extra: `python3 -m pip install "recoverage[report]"`. From a checkout of this repo, `python3 -m pip install -e ".[dev]"` installs the test extra. `python3 -m recoverage` works from that checkout before the first PyPI release exists.

PDF compilation needs the [Typst](https://github.com/typst/typst) CLI on `PATH`. Without it, Markdown and HTML still write and the command continues. A Typst compile error still exits `2`.

## Try the fixture

```bash
python3 -m recoverage run examples/fixture --output examples/sample-report
python3 -m recoverage show examples/sample-report
```

`examples/sample-report/` is a real run of that fixture (MRS 32.5, gate `blocked`, statement coverage 16.7%).

```bash
python3 -m pytest
```

## CLI

```bash
recoverage run [path] [--output DIR] [--dynamic] [--deep] [--threshold GATE|SCORE] [--llm | --no-llm]
recoverage report [path] [--output DIR] [--input analysis.json] [--dynamic] [--deep] [--threshold GATE|SCORE] [--llm | --no-llm]
recoverage generate [path] [--output DIR] [--dry-run] [--dynamic] [--deep] [--llm | --no-llm]
recoverage show [path] [--output DIR] [--port N] [--no-open]
```

Exit code is `1` when `--threshold` is missed, `2` on usage or setup errors, `0` otherwise. The default is static and offline. `--dynamic` runs the project's tests. `--deep` implies `--dynamic` and also runs property, mutation, timing, and search probes out of process. `--llm` is what sends gap metadata to an OpenAI-compatible API. Details are in [docs/cli.md](docs/cli.md).

## Docs

- [Getting started](docs/getting-started.md)
- [CLI](docs/cli.md)
- [Pipeline](docs/pipeline.md)
- [Scoring](docs/scoring.md)
- [Reports](docs/reports.md)
- [Test generation](docs/test-generation.md)
- [Security](docs/security.md)
- [Publishing](docs/pypi.md)
- [CI](docs/ci.md)
- [Roadmap](docs/ROADMAP.md)
- [Changelog](docs/CHANGELOG.md)

## Recoverage score rubric

The score is the Merge Readiness Score (MRS), 0–100. It is the PRD's weighted sum, not a line-coverage percentage.

| Factor | Points | How it is measured |
| --- | --- | --- |
| Structural coverage | 40 | 60% project statement coverage + 40% branch coverage. Unmeasured runtime coverage scores 0. coverage.py's own `percent_covered` is reported beside it and is not the score: with `--branch` that headline blends arcs into statements. |
| Property-based resilience | 25 | Share of property trials that held. The properties are structural conformance, determinism, and entity substitution. The engine runs at least 1,000 inputs when pure functions exist. Failing inputs are shrunk. This is not a frozen expected-output check. |
| Prompt / semantic alignment | 15 | ΔH, the drop in Shannon entropy of specification tokens once tokens named by tests are removed. Offline this is a lexical spotlight, not transformer attention. No spec text scores 0. |
| Blast radius safety | 10 | Union coverage of the call-graph radius. With no diff, the radius is the whole indexed graph and the report says so. |
| Execution-time efficiency | 10 | Mann-Whitney U between baseline inputs and heavier inputs on this revision. Points are lost only when p < 0.05 and the median is more than 8× slower. This is not a cross-commit benchmark. |

Mutation testing is a separate measurement. When it runs, mutants are applied on a temp copy and the kill count is printed. It is not silently folded into MRS. If it does not run, the report says it did not run.

Flake markers found by a static scan subtract 2 points, floored at 0. That scan is not a reproduction. Drafts that `recoverage generate` keeps are executed 5 times in a temp copy before they are copied back.

### Gates

MRS is mapped onto four gates so a CI job can fail below a named bar. The PRD badge uses the same threshold, default 85.

| Gate | Rule |
| --- | --- |
| blocked | No test runner, or measured project statement coverage is below 20%, or MRS is below 40, or the test run did not exit 0. Badge: NOT MERGEABLE. |
| needs-review | A runner exists and MRS is at least 40, but the merge bar is not met. Unmeasured runtime coverage cannot be graded above this gate. |
| merge-ready | MRS ≥ 70, statement coverage ≥ 60%, runtime coverage was measured, and there is no critical gap. Badge: MERGEABLE. |
| production-ready | MRS ≥ 85 (the PRD threshold), statement coverage ≥ 60%, runtime coverage was measured, and there is no critical gap. Badge: PRODUCTION READY. |

`--threshold` accepts a gate name or a number. A gate threshold passes only when the result gate ranks at least that high: blocked < needs-review < merge-ready < production-ready. A numeric threshold passes when MRS is greater than or equal to the number.

### Separate from MRS

CRAP, assertion strength, dependency authenticity, static flakiness risk, and the mutation score are reported on an authenticity scorecard. They are not added into the 100 points and they do not move the gate. A generated draft is kept when it adds covered lines or kills a mutant the existing suite left alive. That filter is there because a coverage bump with a vacuous assertion is not evidence. Drafts still do not lock in an observed return value.
