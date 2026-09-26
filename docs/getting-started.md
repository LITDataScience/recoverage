# Getting started

Python 3.11+. Trusted trees only. Default `run` does not execute the checkout. See [security.md](security.md).

```bash
python3 -m pip install coderecoverage
```

The dashboard and its SVG charts need no extra. `coderecoverage[report]` adds matplotlib PNG charts and the Tree-sitter call graph. `coderecoverage[docs]` builds this site. The install name is `coderecoverage`. The command and the import stay `recoverage`. From a checkout, `python3 -m pip install -e ".[dev]"` installs pytest plus the report extra. The publish steps are in [pypi.md](pypi.md).

## Runtime dependencies

A normal install requires `coverage`. SVG charts are always drawn. PNG charts and the call-graph parser are the `report` extra:

- `matplotlib`
- `tree-sitter`
- `tree-sitter-python`
- `tree-sitter-javascript`

PDF compilation needs the [Typst](https://github.com/typst/typst) CLI (`typst`) on `PATH`, or at `~/.local/bin/typst`. Markdown and HTML are written first. If the Typst binary is missing, the command prints a warning and still exits 0. If `typst compile` fails, the CLI exits `2`.

JavaScript measurement shells out to a local `c8` or `nyc` via `npx --no-install`. Recoverage does not install npm packages.

## GPUs

Recoverage does not use a GPU. NVIDIA, AMD, and Apple GPUs are compatible because they are ignored: parsing, coverage, and probes run on the CPU. CUDA, ROCm, and Metal are not imported and not detected. Apple Silicon needs a normal Python 3.11+ install. A discrete GPU does not make a run faster.

## Try the fixture

`examples/fixture` is a small `shop` package. Its tests cover cart branches, payments, and tier pricing. `examples/sample-report/` is a checked-in `--dynamic` run of that fixture (MRS 60, gate `needs-review`, statement coverage 100%). A `0.1.0` `analysis.json` does not reload on `0.2.0`.

```bash
python3 -m recoverage run examples/fixture --output examples/sample-report --dynamic --no-llm
python3 -m recoverage show examples/sample-report --no-open
```

The checked-in sample is that dynamic run: statement coverage 100%, gate `needs-review`, MRS 60. Deep probes were not requested, so the score stays under the merge bar. Omit `--dynamic` for a static run whose coverage is `not measured`.

`show` serves the `report.html` that `run` already wrote. It does not analyze again. Open `examples/sample-report/report.html` directly if you do not want a local server. `--no-open` skips the browser.

Own tests:

```bash
python3 -m pytest
```

The integration test compiles a real PDF, so Typst has to be installed for the suite to pass.

Read [security.md](security.md) before passing `--dynamic`. That flag executes the checkout as you. There is no OS sandbox.
