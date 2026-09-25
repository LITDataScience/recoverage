# Recoverage docs

Recoverage measures a project, maps gaps onto functions, and scores whether the suite is ready to merge. The package and the CLI are `recoverage`. The design name in the original spec is OmniCov-AI.

These pages describe the code in this checkout. Claims that are not implemented yet are in [ROADMAP.md](ROADMAP.md), not here.

| Page | What it covers |
| --- | --- |
| [Getting started](getting-started.md) | Install, the `report` extra, Typst, the fixture. |
| [Publishing](pypi.md) | Trusted publisher and the release workflow. |
| [CLI](cli.md) | `run`, `report`, `generate`, `show`, exit codes, LLM opt-in, library API. |
| [Pipeline](pipeline.md) | Module map, discovery, coverage adapters, gaps, the in-process graph query. |
| [Scoring](scoring.md) | Merge Readiness Score, gates, authenticity scorecard, known scoring weaknesses. |
| [Reports](reports.md) | Output files, what `analysis.json` stores, Markdown vs HTML escaping, `show`. |
| [Test generation](test-generation.md) | Drafts, the temp-copy filters, and what gets copied back. |
| [Security](security.md) | Trust model. Run this on code you trust. |
| [CI](ci.md) | Gating a project, and what an uploaded report exposes. |
| [Roadmap](ROADMAP.md) | Prioritized work from the security review, with this pass marked done. |
| [Changelog](CHANGELOG.md) | Behavior changes that are not yet released. |
| [CRITIC](CRITIC.md) | The review these docs and the roadmap are answering. |
