"""Self-contained dashboard. Same analysis as the Markdown and PDF. No network."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from recoverage.models import Analysis
from recoverage.reportview import ReportView, build_view
from recoverage.svgcharts import coverage_bars, hotspot_bars, score_gauge, severity_bars

_STYLE = """
:root { color-scheme: light; --bg:#f4f1ea; --ink:#1c1917; --muted:#57534e; --card:#fffcf7; --line:#e7e1d8; --nav:#1f4e79; --chip:#efeae2; }
html[data-theme="dark"] { color-scheme: dark; --bg:#161412; --ink:#f5f0e8; --muted:#a8a29e; --card:#221f1c; --line:#3a342e; --nav:#8eb4d4; --chip:#2c2824; }
@media (prefers-color-scheme: dark) {
  html:not([data-theme="light"]) { color-scheme: dark; --bg:#161412; --ink:#f5f0e8; --muted:#a8a29e; --card:#221f1c; --line:#3a342e; --nav:#8eb4d4; --chip:#2c2824; }
}
* { box-sizing: border-box; }
body { margin: 0; font: 16px/1.5 "Segoe UI", ui-sans-serif, sans-serif; color: var(--ink); background: var(--bg); }
header { position: sticky; top: 0; z-index: 2; display: flex; gap: 20px; align-items: center; padding: 14px 22px; background: var(--card); border-bottom: 1px solid var(--line); }
header svg { width: 140px; height: auto; }
h1 { margin: 0; font-size: 18px; letter-spacing: 0.04em; color: var(--nav); }
.badge { display: inline-block; color: white; font-weight: 700; letter-spacing: 0.05em; font-size: 12px; padding: 4px 8px; border-radius: 4px; }
.meta { color: var(--muted); font-size: 13px; margin: 4px 0 0; }
.layout { display: grid; grid-template-columns: 180px 1fr; }
nav { position: sticky; top: 92px; align-self: start; padding: 16px 12px; }
nav a { display: block; color: var(--nav); text-decoration: none; padding: 6px 8px; border-radius: 6px; font-size: 14px; }
nav a:hover { background: var(--chip); }
main { padding: 8px 28px 64px; max-width: 980px; }
section { margin-top: 28px; }
h2 { font-size: 20px; color: var(--nav); margin: 0 0 10px; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.kpi { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px; }
.kpi b { display: block; font-size: 22px; }
.kpi span { color: var(--muted); font-size: 12px; }
table { width: 100%; border-collapse: collapse; background: var(--card); }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; font-size: 14px; }
th { background: #1f4e79; color: white; font-size: 12px; }
.bar { height: 8px; background: var(--line); border-radius: 4px; overflow: hidden; }
.bar i { display: block; height: 100%; background: #1f7a6b; }
.badge-blocked { background: #9b2335; }
.badge-needs-review { background: #c47b00; }
.badge-merge-ready { background: #1f4e79; }
.badge-production-ready { background: #1e7a46; }
""" + "".join(f".w{step} {{ width: {step}%; }}" for step in range(0, 101, 5)) + """
.finding { background: var(--card); padding: 12px 14px; margin: 10px 0; border-left: 4px solid #1f4e79; border-radius: 0 8px 8px 0; }
.finding.critical { border-color: #9b2335; }
.finding.high { border-color: #d35400; }
.finding.medium { border-color: #c47b00; }
.finding.low { border-color: #2e6b9a; }
.tools { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
button, .chip { font: inherit; border: 1px solid var(--line); background: var(--chip); color: var(--ink); border-radius: 999px; padding: 4px 10px; cursor: pointer; }
button[aria-pressed="true"] { background: #1f4e79; color: white; }
input { font: inherit; padding: 6px 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--card); color: var(--ink); }
.hidden { display: none; }
.file-detail { background: var(--bg); }
code { font-family: ui-monospace, monospace; font-size: 0.92em; }
svg.chart { width: 100%; height: auto; background: var(--card); border-radius: 8px; }
@media (max-width: 800px) { .layout { grid-template-columns: 1fr; } nav { position: static; display: flex; flex-wrap: wrap; } .kpis { grid-template-columns: 1fr 1fr; } header { position: static; } }
@media print { header, nav, .tools, button { display: none; } .layout { display: block; } body { background: white; } }
"""

_SCRIPT = """
(function () {
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem("recoverage-theme"); } catch (err) { stored = null; }
  if (stored === "dark" || stored === "light") root.setAttribute("data-theme", stored);
  var toggle = document.getElementById("theme");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      if (!root.getAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches) next = "light";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("recoverage-theme", next); } catch (err) { return; }
    });
  }
  var findings = Array.prototype.slice.call(document.querySelectorAll("#findings article"));
  var chips = Array.prototype.slice.call(document.querySelectorAll("[data-filter]"));
  var query = document.getElementById("finding-filter");
  var count = document.getElementById("finding-count");
  var active = "all";
  function apply() {
    var needle = (query && query.value || "").toLowerCase();
    var shown = 0;
    findings.forEach(function (card) {
      var text = (card.getAttribute("data-search") || "").toLowerCase();
      var severity = card.getAttribute("data-severity");
      var kind = card.getAttribute("data-kind");
      var ok = (active === "all" || active === severity || active === kind) && text.indexOf(needle) !== -1;
      card.classList.toggle("hidden", !ok);
      if (ok) shown += 1;
    });
    if (count) count.textContent = String(shown);
  }
  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      active = chip.getAttribute("data-filter") || "all";
      chips.forEach(function (other) { other.setAttribute("aria-pressed", other === chip ? "true" : "false"); });
      apply();
    });
  });
  if (query) query.addEventListener("input", apply);
  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var card = button.closest("article");
      var node = card ? card.querySelector(".suggestion") : null;
      var text = node ? node.textContent : "";
      if (navigator.clipboard) navigator.clipboard.writeText(text);
    });
  });
  document.querySelectorAll("[data-file]").forEach(function (row) {
    row.addEventListener("click", function () {
      var detail = document.getElementById("detail-" + row.getAttribute("data-file"));
      if (detail) detail.classList.toggle("hidden");
    });
  });
})();
"""


def write_html(analysis: Analysis, path: Path, charts: dict[str, Path] | None = None) -> Path:
    del charts
    path.write_text(build_html(analysis, {}), encoding="utf-8")
    return path


def build_html(analysis: Analysis, charts: dict[str, Path] | None = None) -> str:
    del charts
    view = build_view(analysis)
    style_hash = _csp( _STYLE)
    script_hash = _csp(_SCRIPT)
    payload = _payload(view, analysis)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src '{style_hash}'; script-src '{script_hash}'">
<title>Recoverage {html.escape(f"{view.score:.1f}")} {html.escape(view.gate)}</title>
<style>{_STYLE}</style>
</head>
<body>
<header>
  <div>{score_gauge(view)}</div>
  <div>
    <h1>Recoverage · {html.escape(view.project_name)}</h1>
    <p><span class="badge badge-{html.escape(view.gate)}">{html.escape(view.badge)}</span></p>
    <p class="meta">{html.escape(view.gate_sentence)}</p>
    <p class="meta">{html.escape(view.language)} · runner {html.escape(view.test_runner)} · {html.escape(view.coverage_tool)} · {html.escape(view.generated_at)} · LLM {html.escape(view.llm)}</p>
  </div>
  <button id="theme" type="button">Theme</button>
</header>
<div class="layout">
<nav>
  <a href="#overview">Overview</a>
  <a href="#coverage">Coverage</a>
  <a href="#findings">Findings</a>
  <a href="#files">Files</a>
  <a href="#hotspots">Hotspots</a>
  <a href="#authenticity">Authenticity</a>
  <a href="#analytics">Analytics</a>
  <a href="#suggestions">Suggestions</a>
  <a href="#rubric">Rubric</a>
</nav>
<main>
<section id="overview">
  <h2>Overview</h2>
  <div class="kpis">
    <div class="kpi"><b>{html.escape(_pct(view.line_percent))}</b><span>Statement coverage</span></div>
    <div class="kpi"><b>{html.escape(_pct(view.branch_percent))}</b><span>Branch coverage</span></div>
    <div class="kpi"><b>{sum(view.severity_counts.values())}</b><span>Gaps · {view.severity_counts["critical"]} critical</span></div>
    <div class="kpi"><b>{"yes" if view.mutation_ran else "no"}</b><span>Mutation ran</span></div>
  </div>
  {"".join(f"<p>{html.escape(note)}</p>" for note in view.notes)}
  <h2>Score factors</h2>
  <table>
    <tr><th>Factor</th><th>Earned</th><th></th><th>Detail</th></tr>
    {"".join(_factor(row) for row in view.factors)}
  </table>
</section>
<section id="coverage">
  <h2>Coverage</h2>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    {"".join(f"<tr><td>{html.escape(row.metric)}</td><td>{html.escape(row.value)}</td></tr>" for row in view.coverage_rows)}
  </table>
  {coverage_bars(view)}
  {severity_bars(view)}
</section>
<section id="findings">
  <h2>Findings</h2>
  <div class="tools">
    <button type="button" data-filter="all" aria-pressed="true">All</button>
    <button type="button" data-filter="critical" aria-pressed="false">Critical</button>
    <button type="button" data-filter="high" aria-pressed="false">High</button>
    <button type="button" data-filter="medium" aria-pressed="false">Medium</button>
    <button type="button" data-filter="low" aria-pressed="false">Low</button>
    <input id="finding-filter" type="search" placeholder="Filter findings" aria-label="Filter findings">
    <span id="finding-count">{len(view.findings)}</span>
  </div>
  {_findings_html(view)}
</section>
<section id="files">
  <h2>Files</h2>
  {_files_html(view, analysis)}
</section>
<section id="hotspots">
  <h2>Hotspots</h2>
  {hotspot_bars(view)}
  {_hotspot_table(view)}
</section>
<section id="authenticity">
  <h2>Authenticity</h2>
  <p>{html.escape(view.audit_note)}</p>
  {_audit_table(view)}
  <p>{html.escape(view.assertion_note)}</p>
  {_crap_table(view)}
</section>
<section id="analytics">
  <h2>Analytics</h2>
  <p>{html.escape(view.pbt_note)}</p>
  {_pbt_table(view)}
  <p>{html.escape(view.mutation_note)}</p>
  <p>{html.escape(view.prompt_note)}</p>
  <p>{html.escape(view.blast_note)} Union coverage: {html.escape(_pct(view.blast_union))}.</p>
  <p>{html.escape(view.timing_note)}</p>
  <p>Tree-sitter index: {"yes" if view.tree_sitter else "no"}. Entities: {view.entity_count}. Communities: {view.community_count}.</p>
</section>
<section id="suggestions">
  <h2>Suggestions</h2>
  <ul>
    {"".join(f"<li>{html.escape(line)}</li>" for line in view.suggestions)}
  </ul>
</section>
<section id="rubric">
  <h2>Rubric</h2>
  <pre>{html.escape(view.rubric)}</pre>
</section>
</main>
</div>
<script type="application/json" id="recoverage-data">{payload}</script>
<script>{_SCRIPT}</script>
</body>
</html>
"""


def _csp(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).digest()
    import base64

    return "sha256-" + base64.b64encode(digest).decode("ascii")


def _payload(view: ReportView, analysis: Analysis) -> str:
    body = {
        "score": view.score,
        "gate": view.gate,
        "findings": [
            {"id": item.id, "severity": item.severity, "kind": item.kind, "symbol": item.symbol, "file": item.file}
            for item in view.findings
        ],
        "files": [row.path for row in view.files],
    }
    del analysis
    text = json.dumps(body, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _pct(value: float | None) -> str:
    if value is None:
        return "not measured"
    return f"{value:.1f}%"


def _factor(row) -> str:
    width = 0 if row.maximum <= 0 else min(100.0, 100.0 * row.earned / row.maximum)
    step = int(round(width / 5.0) * 5)
    return (
        "<tr>"
        f"<td>{html.escape(row.title)}</td>"
        f"<td>{row.earned:.2f} / {row.maximum:.0f}</td>"
        f'<td><div class="bar"><i class="w{step}"></i></div></td>'
        f"<td>{html.escape(row.detail)}</td>"
        "</tr>"
    )


def _findings_html(view: ReportView) -> str:
    if not view.findings:
        return "<p>No gaps recorded.</p>"
    blocks = []
    for gap in view.findings:
        where = html.escape(gap.file or "project")
        symbol = f" <code>{html.escape(gap.symbol)}</code>" if gap.symbol else ""
        search = html.escape(" ".join(filter(None, (gap.id, gap.severity, gap.kind, gap.title, gap.file, gap.symbol, gap.why))))
        blocks.append(
            f'<article class="finding {html.escape(gap.severity)}" data-severity="{html.escape(gap.severity)}" '
            f'data-kind="{html.escape(gap.kind)}" data-search="{search}">'
            f"<h3>{html.escape(gap.id)} · {html.escape(gap.severity)} · {html.escape(gap.title)}</h3>"
            f"<p><code>{where}</code>{symbol}</p>"
            f"<p>{html.escape(gap.why)}</p>"
            f'<p class="suggestion">{html.escape(gap.suggestion)}</p>'
            '<p><button type="button" data-copy="1">Copy suggestion</button></p>'
            "</article>"
        )
    return "\n".join(blocks)


def _files_html(view: ReportView, analysis: Analysis) -> str:
    if not view.files:
        return "<p>No files.</p>"
    by_file: dict[str, list] = {}
    for function in analysis.functions:
        by_file.setdefault(function.spec.file, []).append(function)
    rows = []
    for index, row in enumerate(view.files):
        percent = "not measured" if row.line_percent is None else f"{row.line_percent:.1f}%"
        worst = row.worst_gap or "—"
        rows.append(
            f'<tr data-file="{index}">'
            f"<td><code>{html.escape(row.path)}</code></td><td>{row.statements}</td><td>{html.escape(percent)}</td>"
            f"<td>{row.functions}</td><td>{row.gaps}</td><td>{html.escape(worst)}</td></tr>"
            f'<tr id="detail-{index}" class="hidden file-detail"><td colspan="6">{_function_lines(by_file.get(row.path, []))}</td></tr>'
        )
    return (
        "<table><tr><th>File</th><th>Statements</th><th>Coverage</th><th>Functions</th><th>Gaps</th><th>Worst</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _function_lines(functions: list) -> str:
    if not functions:
        return "No mapped functions."
    lines = []
    for function in functions:
        ratio = "n/a" if function.coverage_ratio is None else f"{function.coverage_ratio:.0%}"
        missing = ", ".join(str(line) for line in function.missing_lines[:12]) or "none"
        lines.append(
            f"<p><code>{html.escape(function.spec.qualname)}</code> coverage {html.escape(ratio)}; missing {html.escape(missing)}</p>"
        )
    return "".join(lines)


def _hotspot_table(view: ReportView) -> str:
    if not view.hotspots:
        return "<p>No hotspots.</p>"
    rows = []
    for spot in view.hotspots:
        coverage = "n/a" if spot.coverage_ratio is None else f"{spot.coverage_ratio:.0%}"
        tags = ", ".join(spot.risk_tags) or "—"
        rows.append(
            f"<tr><td><code>{html.escape(spot.qualname)}</code></td><td><code>{html.escape(spot.file)}</code></td>"
            f"<td>{spot.risk_score:.2f}</td><td>{html.escape(coverage)}</td><td>{html.escape(tags)}</td></tr>"
        )
    return "<table><tr><th>Function</th><th>File</th><th>Risk</th><th>Coverage</th><th>Tags</th></tr>" + "".join(rows) + "</table>"


def _audit_table(view: ReportView) -> str:
    if not view.audit_rows:
        return ""
    rows = "".join(
        f"<tr><td>{html.escape(row.dimension)}</td><td>{html.escape(row.value)}</td>"
        f"<td>{html.escape(row.threshold)}</td><td>{html.escape(row.status)}</td></tr>"
        for row in view.audit_rows
    )
    return "<table><tr><th>Dimension</th><th>Value</th><th>Threshold</th><th>Status</th></tr>" + rows + "</table>"


def _crap_table(view: ReportView) -> str:
    if not view.crap_rows:
        return ""
    rows = []
    for row in view.crap_rows:
        coverage = "n/a" if row.get("coverage") is None else f"{row['coverage']:.0%}"
        rows.append(
            f"<tr><td><code>{html.escape(str(row.get('symbol')))}</code></td><td>{row.get('complexity')}</td>"
            f"<td>{html.escape(coverage)}</td><td>{row.get('crap')}</td></tr>"
        )
    return "<table><tr><th>Function</th><th>Complexity</th><th>Coverage</th><th>CRAP</th></tr>" + "".join(rows) + "</table>"


def _pbt_table(view: ReportView) -> str:
    if not view.pbt_rows:
        return ""
    rows = "".join(
        f"<tr><td><code>{html.escape(row.symbol)}</code></td><td>{row.trials}</td><td>{row.passed}</td><td>{row.failed}</td></tr>"
        for row in view.pbt_rows
    )
    return "<table><tr><th>Symbol</th><th>Trials</th><th>Passed</th><th>Failed</th></tr>" + rows + "</table>"
