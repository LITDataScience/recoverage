# Roadmap

`0.1.0` is on PyPI as `coderecoverage`. This tree is `0.2.0` (dashboard, SVG charts, MkDocs site) and is not tagged yet. Cut it with Actions → **Release** after CI is green. Steps are in [pypi.md](pypi.md).

There is still no OS container. `--dynamic` and `--deep` run the checkout as you. The README says so.

## Done

What shipped: static default, scrubbed `analysis.json`, version and size checks, probes out of process, `--deep` for property/mutation/timing/search, `coverage` as the only required dependency, SVG charts without matplotlib, a one-file dashboard, host budgets that follow CPU and RAM, and the publish workflow that uploads the wheel it tested. `0.1.0` was published from that workflow. Review notes stay on the maintainer's machine. They are not part of this site.

## Still open

- **HOST-01..03.** Done. Budgets scale with the machine. One probe worker. The parse pool is threads, not a native parser.
- **SEC-06.** `SourceCache` is an LRU (64 MB on an 8 GB machine, less below 4 GB, 128 MB on a large machine) cleared at the end of `run_analysis`. A library caller that raises mid-run keeps that memory until the frame is collected.
- **PERF-13.** Python files are parsed with `ast` and again with Tree-sitter. One intermediate representation would remove the second parse. A Rust parser stays out of the required install.
- **PERF-14.** Louvain is the naive local-move loop. It is fine at the discovery cap.
- No OS container, network namespace, or read-only filesystem for `--dynamic`.

## Explicitly not the next step

Do not describe the temp copy as a sandbox. Do not upload a wheel that `python-publish.yml` did not build. Do not `git tag` by hand.
