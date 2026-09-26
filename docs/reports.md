# Reports

`run` and `report` write these from the same analysis:

| File | What it is |
| --- | --- |
| `report.html` | One-file dashboard. Inline SVG charts, filters, a theme toggle, and a file table. A Content-Security-Policy allows only the hashes of its own style and script. No stylesheet link, no script source, no network. The page still reads with JavaScript disabled. |
| `report.md` | The same sections: overview, coverage, factors, findings grouped by severity, files, suggestions, rubric. Charts are SVG links. |
| `report.pdf` | Typst render of `mrs.json`. Cover, contents, files (capped), findings. Not a screenshot of the HTML. |
| `report.typ` | Copy of the package template, next to `mrs.json`, because `typst compile` runs in the output directory. |
| `charts/*.svg` | `score_gauge`, `coverage_by_package`, `risk_hotspots`, `gap_severity`. Drawn by Recoverage. No matplotlib. |
| `charts/*.png` | The same three bar charts, only when matplotlib is installed (`coderecoverage[report]` or `[dev]`). Markdown prefers the SVG. |
| `analysis.json` | Full analysis. `report` and `generate` load it only when `version` equals this package, the required keys are present, and the file is at most 100 MB. A 0.1.0 file does not load on 0.2.0. |
| `coverage.json` | coverage.py JSON, copied into the output directory when the Python adapter measured a run. The SQLite `.coverage` file stays in a temp directory that is removed when the run finishes. JS writes `js-coverage/` in that same kind of temp directory. |
| `mrs.json` | Numbers the PDF template reads: gate sentence, files, findings, suggestions. |
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

HTML escapes gap text, factor details, and suggestions, and embeds the interactive data as JSON with `<` escaped. The script builds nodes with `textContent`. Markdown escapes gap title, why, and suggestion so they do not become links or images. Do not host a report from a tree you do not trust.

The PDF view is the same projection as the dashboard, shortened: cover, factors, module bars, severity counts, up to 60 files, findings, PBT rows, one-line notes, the audit scorecard, suggestions, and the rubric. It does not embed SBST arguments.

## `show`

`serve_html` binds `127.0.0.1` and serves the HTML bytes and `charts/*.svg` it read at startup. Any other path is 404. Any local process that can connect to that port can read the report. The server runs until Ctrl-C. Reports include project metadata; treat the port as private to the user who started it.

## Retention

`examples/ci/recoverage.yml` uploads `analysis.json` as a GitHub artifact. Artifact permissions and retention are part of the privacy boundary. Prefer uploading `report.md` / `report.pdf` / `charts/` only, unless you have read [security.md](security.md) and accept the JSON contents above.
