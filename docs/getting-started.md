# Getting started

Python 3.11+. Trusted trees only. Default `run` does not execute the checkout. See [security.md](security.md).

```bash
python3 -m pip install recoverage
```

`recoverage[report]` adds matplotlib and Tree-sitter. From a checkout, `python3 -m pip install -e ".[dev]"` installs pytest plus that extra. `python3 -m recoverage` works from the checkout before the first release is on PyPI. The publish steps are in [pypi.md](pypi.md).

## Runtime dependencies

A normal install requires `coverage`. Charts and the call-graph parser are the `report` extra:

- `matplotlib`
- `tree-sitter`
- `tree-sitter-python`
- `tree-sitter-javascript`

PDF compilation needs the [Typst](https://github.com/typst/typst) CLI (`typst`) on `PATH`, or at `~/.local/bin/typst`. Markdown and HTML are written first. If the Typst binary is missing, the command prints a warning and still exits 0. If `typst compile` fails, the CLI exits `2`.

JavaScript measurement shells out to a local `c8` or `nyc` via `npx --no-install`. Recoverage does not install npm packages.

## Try the fixture

`examples/fixture` is a small `shop` package. `tests/test_cart.py` covers one happy path. Payments and pricing are untested. `examples/sample-report/` is a checked-in run of that fixture (MRS 32.5, gate `blocked`, statement coverage 16.7%). Paths in that sample are project-relative.

```bash
python3 -m recoverage run examples/fixture --output examples/sample-report
python3 -m recoverage show examples/sample-report
```

`show` serves the `report.html` that `run` already wrote. It does not analyze again. Open `examples/sample-report/report.html` directly if you do not want a local server. `--no-open` skips the browser.

Own tests:

```bash
python3 -m pytest
```

The integration test compiles a real PDF, so Typst has to be installed for the suite to pass.

Read [security.md](security.md) before passing `--dynamic`. That flag executes the checkout as you. There is no OS sandbox.
