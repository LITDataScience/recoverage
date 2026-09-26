# Recoverage

Recoverage measures a project, maps gaps onto functions, and scores whether the suite is ready to merge. The package on PyPI is `coderecoverage` (`0.1.0`). This checkout is `0.2.0`: the HTML report is a single-file dashboard, charts are SVG, and these pages are the MkDocs site. The command and the import are `recoverage`.

```bash
python3 -m pip install coderecoverage
recoverage run .
```

Default `run` is static. It does not import the project or start a test runner. `--dynamic` runs the tests as you. There is no OS sandbox. Read [Security](security.md) before pointing it at a checkout.

| Start here | |
| --- | --- |
| [Getting started](getting-started.md) | Install, the `report` extra, Typst, the fixture. |
| [CLI](cli.md) | `run`, `report`, `generate`, `show`, `docs`. |
| [Reports](reports.md) | Files a run writes. |
| [Report anatomy](report-anatomy.md) | What each dashboard section means, and what it does not claim. |
| [Publishing](pypi.md) | How a tag becomes a PyPI release. |

`recoverage docs` opens this site. `recoverage docs --offline` prints the `docs/` directory when you are in a git checkout.
