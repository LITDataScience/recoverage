# Reports

`run` and `report` write these from the same analysis:

| File | What it is |
| --- | --- |
| `report.md` | Score, gate sentence, coverage, findings, suggestions, charts as PNG links, rubric. |
| `report.html` | Same coverage, factors, findings, and suggestions in one file. Inline CSS. Charts are `data:image/png;base64` URIs. No external stylesheet or script. Opens with no server. |
| `report.pdf` | Typst render of `mrs.json`. Vector bars, not a screenshot of the HTML. |
| `report.typ` | Copy of the package template, next to `mrs.json`, because `typst compile` runs in the output directory. |
| `charts/*.png` | `coverage_by_package`, `risk_hotspots`, `gap_severity`. Matplotlib. Used by the Markdown. |
| `analysis.json` | Full analysis. `report` and `generate` will load it back with no schema check. |
| `coverage.json` | coverage.py output, when the Python adapter got that far. JS writes `js-coverage/` instead. |
| `mrs.json` | Numbers the PDF template reads, including the gate sentence and suggestion lines. |
| `.coverage` | coverage.py's data file, in the output directory via `COVERAGE_FILE`. Not cleared before the next run. |
| `generation-preview.md` | Only after `generate`. Draft source in fences. |
| `generation-manifest.json` | Only after `generate`. `dry_run` and the paths that were planned or written. |

## What `analysis.json` contains

`analysis_to_dict` dumps every field:

- `project.root` and `project.import_root` reduced to a basename when they were absolute.
- Source and test paths, entry points, flake-marker locations.
- Function signatures, parameters, risk tags, statement line lists. Docstrings are blanked.
- The coverage command argv, the test exit code, and coverage notes. Test stdout and stderr tails are not stored.
- Gap `why` and `suggestion` text, including LLM rewrites when `--llm` was used.
- Call-graph entities: file, byte range, signature. PageRank, communities, edges.
- SBST cases: argument type names, or `<redacted>` for a secret-shaped string. See [test-generation.md](test-generation.md).
- PBT falsifying inputs, mutation descriptions, timing ratios, audit rows.

The file is scrubbed before write and written compact (no indentation; `python -m json.tool analysis.json` pretty-prints it). `report` and `generate` load it with a version check, a required-key check, and a 100_000_000 byte cap. A mismatch raises `ValueError` and the CLI exits 2. Unexpected keys on a dataclass still raise `TypeError`.

## Rendering

HTML escapes gap text, factor details, and suggestions. Markdown escapes gap title, why, and suggestion so they do not become links or images. Do not host a report from a tree you do not trust.

The PDF view is a reduced projection: score, factors, module percents, severity counts, PBT rows, one-line notes, audit scorecard, suggestions, rubric. It does not embed SBST arguments.

## `show`

`serve_html` binds `127.0.0.1` and serves the HTML bytes it read at startup. Any local process that can connect to that port can read the report. The server runs until Ctrl-C. Reports include project metadata; treat the port as private to the user who started it.

## Retention

`examples/ci/recoverage.yml` uploads `analysis.json` as a GitHub artifact. Artifact permissions and retention are part of the privacy boundary. Prefer uploading `report.md` / `report.pdf` / `charts/` only, unless you have read [security.md](security.md) and accept the JSON contents above.
