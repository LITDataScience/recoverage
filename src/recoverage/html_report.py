"""Self-contained HTML report. Same analysis as the Markdown and PDF."""

from __future__ import annotations

import base64
import html
from pathlib import Path

from recoverage.models import Analysis
from recoverage.report import _badge, _gate_sentence, _suggestions

_BADGE_COLOR = {
    "blocked": "#9b2335",
    "needs-review": "#c47b00",
    "merge-ready": "#1f4e79",
    "production-ready": "#1e7a46",
}


def write_html(analysis: Analysis, path: Path, charts: dict[str, Path]) -> Path:
    path.write_text(build_html(analysis, charts), encoding="utf-8")
    return path


def build_html(analysis: Analysis, charts: dict[str, Path]) -> str:
    score = analysis.score
    coverage = analysis.coverage
    color = _BADGE_COLOR.get(score.gate, "#1f4e79")
    line = "not measured" if coverage.line_percent is None else f"{coverage.line_percent:.1f}%"
    branch = "not measured" if coverage.branch_percent is None else f"{coverage.branch_percent:.1f}%"
    findings = _html_findings(analysis)
    suggestions = _html_suggestions(analysis)
    images = "\n".join(_chart(name, charts.get(name)) for name in ("coverage_by_package", "risk_hotspots", "gap_severity"))
    factors = "\n".join(
        "<tr>"
        f"<td>{html.escape(factor.title)}</td>"
        f"<td>{factor.earned:.2f}</td>"
        f"<td>{factor.maximum:.0f}</td>"
        f"<td>{html.escape(factor.detail)}</td>"
        "</tr>"
        for factor in score.factors
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Recoverage {html.escape(f"{score.score:.1f}")} {html.escape(score.gate)}</title>
<style>
:root {{ color-scheme: light; }}
body {{ margin: 0; font: 16px/1.45 Georgia, "Iowan Old Style", serif; color: #1c1917; background: #f6f3ee; }}
main {{ max-width: 880px; margin: 0 auto; padding: 32px 20px 64px; }}
header {{ background: #1f4e79; color: white; padding: 28px 20px 32px; }}
header h1 {{ margin: 0; font-family: "Segoe UI", sans-serif; font-size: 22px; letter-spacing: 0.04em; }}
.score {{ font-family: "Segoe UI", sans-serif; font-size: 64px; font-weight: 700; line-height: 1; margin: 12px 0 8px; }}
.badge {{ display: inline-block; background: {color}; color: white; font-family: "Segoe UI", sans-serif; font-weight: 700; letter-spacing: 0.06em; padding: 6px 12px; border-radius: 4px; }}
section {{ margin-top: 28px; }}
h2 {{ font-family: "Segoe UI", sans-serif; font-size: 20px; color: #1f4e79; margin-bottom: 8px; }}
table {{ width: 100%; border-collapse: collapse; background: white; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #e7e1d8; vertical-align: top; }}
th {{ font-family: "Segoe UI", sans-serif; font-size: 13px; background: #1f4e79; color: white; }}
img {{ max-width: 100%; height: auto; background: white; }}
.finding {{ background: white; padding: 12px 14px; margin: 10px 0; border-left: 4px solid #1f4e79; }}
.finding.critical {{ border-color: #9b2335; }}
.finding.high {{ border-color: #d35400; }}
ul {{ padding-left: 20px; }}
code {{ font-family: ui-monospace, monospace; font-size: 0.92em; }}
</style>
</head>
<body>
<header>
  <h1>Recoverage</h1>
  <div class="score">{html.escape(f"{score.score:.1f}")}<span style="font-size:22px;font-weight:400"> / 100</span></div>
  <div class="badge">{html.escape(_badge(score.gate))}</div>
  <p>Gate: {html.escape(score.gate)}</p>
  <p>{html.escape(_gate_sentence(analysis))}</p>
</header>
<main>
<section>
  <h2>Coverage</h2>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Project statement coverage</td><td>{html.escape(line)}</td></tr>
    <tr><td>Branch coverage</td><td>{html.escape(branch)}</td></tr>
    <tr><td>Test runner</td><td>{html.escape(analysis.project.test_runner or "none")}</td></tr>
    <tr><td>Coverage tool</td><td>{html.escape(coverage.tool)}</td></tr>
    <tr><td>Measured</td><td>{"yes" if coverage.measured else "no"}</td></tr>
  </table>
  {"".join(f"<p>{html.escape(note)}</p>" for note in analysis.project.notes)}
</section>
<section>
  <h2>Score factors</h2>
  <table>
    <tr><th>Factor</th><th>Earned</th><th>Max</th><th>Detail</th></tr>
    {factors}
  </table>
</section>
<section>
  <h2>Charts</h2>
  {images}
</section>
<section>
  <h2>Findings</h2>
  {findings}
</section>
<section>
  <h2>Suggestions</h2>
  {suggestions}
</section>
</main>
</body>
</html>
"""


def _chart(name: str, path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    encoded = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    label = html.escape(name.replace("_", " "))
    return f'<figure><img alt="{label}" src="data:image/png;base64,{encoded}"></figure>'


def _html_findings(analysis: Analysis) -> str:
    if not analysis.gaps:
        return "<p>No gaps recorded.</p>"
    blocks = []
    for gap in analysis.gaps:
        where = html.escape(gap.file or "project")
        symbol = f" <code>{html.escape(gap.symbol)}</code>" if gap.symbol else ""
        blocks.append(
            f'<article class="finding {html.escape(gap.severity)}">'
            f"<h3>{html.escape(gap.id)} · {html.escape(gap.severity)} · {html.escape(gap.title)}</h3>"
            f"<p><code>{where}</code>{symbol}</p>"
            f"<p>{html.escape(gap.why)}</p>"
            f"<p>{html.escape(gap.suggestion)}</p>"
            "</article>"
        )
    return "\n".join(blocks)


def _html_suggestions(analysis: Analysis) -> str:
    text = _suggestions(analysis)
    items = []
    paragraphs = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(f"<li>{html.escape(stripped[2:])}</li>")
        elif stripped:
            paragraphs.append(f"<p>{html.escape(stripped)}</p>")
    rendered = "\n".join(paragraphs)
    if items:
        rendered += "\n<ul>\n" + "\n".join(items) + "\n</ul>"
    return rendered or "<p>No suggestions.</p>"
