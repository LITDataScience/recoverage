"""Markdown report. The PDF is compiled from the same analysis by Typst."""

from __future__ import annotations

import re
from pathlib import Path

from recoverage.models import Analysis
from recoverage.score import RUBRIC_MD, explain_gate
from recoverage.typst_render import write_typst_pdf

_GATE_HEX = {
    "blocked": "#9B2335",
    "needs-review": "#C47B00",
    "merge-ready": "#1F4E79",
    "production-ready": "#1E7A46",
}


def build_markdown(analysis: Analysis) -> str:
    score = analysis.score
    coverage = analysis.coverage
    lines = [
        "# Recoverage report",
        "",
        f"**Merge Readiness Score: {score.score:.1f} / 100**  ",
        f"**Gate: `{score.gate}`**  ",
        f"**Badge: `{_badge(score.gate)}`**",
        "",
        _gate_sentence(analysis),
        "",
        f"Project: `{analysis.project.root}`  ",
        f"Language: {analysis.project.primary_language}  ",
        f"Test runner: {analysis.project.test_runner or 'none'}  ",
        f"Coverage tool: {coverage.tool}  ",
        f"LLM: {analysis.llm}  ",
        f"Generated: {analysis.generated_at}",
        "",
        f"<!-- recoverage:score={score.score:.1f};gate={score.gate};mutation={'true' if score.mutation_testing_ran else 'false'} -->",
        "",
        "## Coverage stats",
        "",
        _coverage_table(analysis),
        "",
        "## Score factors",
        "",
        _factor_table(analysis),
        "",
        _analytics_sections(analysis),
        "",
        "## Coverage by package",
        "",
        "{{chart:coverage_by_package}}",
        "",
        "## Risk hotspots",
        "",
        "{{chart:risk_hotspots}}",
        "",
        _hotspot_table(analysis),
        "",
        "## Gap severity",
        "",
        "{{chart:gap_severity}}",
        "",
        "## Findings",
        "",
        _findings(analysis),
        "",
        "## Suggestions",
        "",
        _suggestions(analysis),
        "",
        RUBRIC_MD.strip(),
        "",
    ]
    return "\n".join(lines)


def write_reports(analysis: Analysis, output_dir: Path, charts: dict[str, Path]) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown = build_markdown(analysis)
    md_path = output_dir / "report.md"
    pdf_path = output_dir / "report.pdf"
    html_path = output_dir / "report.html"
    md_path.write_text(_markdown_with_images(markdown, charts, md_path), encoding="utf-8")
    from recoverage.html_report import write_html

    write_html(analysis, html_path, charts)
    write_typst_pdf(analysis, output_dir)
    return md_path, pdf_path, html_path


def _gate_sentence(analysis: Analysis) -> str:
    coverage = analysis.coverage
    return explain_gate(
        analysis.score.gate,
        score=analysis.score.score,
        runner=bool(analysis.project.test_runner),
        measured=coverage.measured,
        line=coverage.line_percent,
        critical=sum(1 for gap in analysis.gaps if gap.severity == "critical"),
    )


def _markdown_with_images(markdown: str, charts: dict[str, Path], md_path: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        chart = charts[key]
        relative = chart.relative_to(md_path.parent).as_posix()
        return f"![{key.replace('_', ' ')}]({relative})"

    return re.sub(r"\{\{chart:([a-z0-9_]+)\}\}", replace, markdown)


def _coverage_table(analysis: Analysis) -> str:
    coverage = analysis.coverage
    rows = [
        "| Metric | Value |",
        "| --- | --- |",
        f"| Project statement coverage | {_pct(coverage.line_percent)} |",
        f"| Tool percent_covered | {_pct(coverage.tool_line_percent)} |",
        f"| Branch coverage | {_pct(coverage.branch_percent)} |",
        f"| Branch figure is runtime-tool-only | {'yes' if coverage.branch_is_tool else 'no'} |",
        f"| Tool | {coverage.tool} |",
        f"| Measured | {'yes' if coverage.measured else 'no'} |",
        f"| Test exit code | {coverage.tests_exit_code if coverage.tests_exit_code is not None else 'n/a'} |",
    ]
    return "\n".join(rows)


def _factor_table(analysis: Analysis) -> str:
    rows = ["| Factor | Earned | Max | Heuristic | Detail |", "| --- | --- | --- | --- | --- |"]
    for factor in analysis.score.factors:
        detail = factor.detail.replace("|", "/")
        rows.append(
            f"| {factor.title} | {factor.earned:.2f} | {factor.maximum:.0f} | "
            f"{'yes' if factor.heuristic else 'no'} | {detail} |"
        )
    return "\n".join(rows)


def _hotspot_table(analysis: Analysis) -> str:
    if not analysis.hotspots:
        return "No hotspots."
    rows = ["| Function | File | Risk | Coverage | Tags |", "| --- | --- | --- | --- | --- |"]
    for spot in analysis.hotspots:
        coverage = "n/a" if spot.coverage_ratio is None else f"{spot.coverage_ratio:.0%}"
        tags = ", ".join(spot.risk_tags) or "—"
        rows.append(
            f"| `{spot.qualname}` | `{spot.file}` | {spot.risk_score:.2f} | {coverage} | {tags} |"
        )
    return "\n".join(rows)


def _findings(analysis: Analysis) -> str:
    if not analysis.gaps:
        return "No gaps recorded."
    blocks = []
    for gap in analysis.gaps:
        where = f"`{gap.file}`" if gap.file else "project"
        symbol = f" `{gap.symbol}`" if gap.symbol else ""
        heuristic = " Heuristic." if gap.heuristic else ""
        llm = " LLM-enriched." if gap.llm_enriched else ""
        blocks.append(
            f"### {gap.id} · {gap.severity} · {gap.title}\n\n"
            f"{where}{symbol}. Kind: `{gap.kind}`.{heuristic}{llm}\n\n"
            f"{gap.why}\n\n"
            f"Suggestion: {gap.suggestion}"
        )
    return "\n\n".join(blocks)


def _suggestions(analysis: Analysis) -> str:
    """Developer-facing next actions. Not a restatement of the score."""
    lines = [
        "Read the findings from the top. Critical and high items are the ones that move the gate.",
        "",
        "- `recoverage generate` keeps a draft only after a sandbox compile and 5 passing runs, and only if it adds covered lines or kills a mutant the current suite left alive. It does not lock in observed return values.",
        "- Recoverage will not delete or overwrite an existing test file.",
        "- Prompt coverage ΔH is a lexical entropy proxy unless an attention model is actually queried. The report names which one ran.",
        "- Mutation counts come from temp-copy mutants. If that section says mutation did not run, it did not.",
    ]
    if not analysis.coverage.measured:
        if analysis.project.primary_language == "python":
            lines.append("- Runtime coverage did not run. Install `coverage` and make the tests import the package under test.")
        elif analysis.project.primary_language in {"javascript", "typescript"}:
            lines.append("- Runtime coverage did not run. Install `c8` or `nyc` locally, then re-run. Recoverage will not `npm install` for you.")
        else:
            lines.append("- This language has static structure analysis only. There is no runtime coverage number to chase yet.")
    crap_rows = ((analysis.analytics or {}).get("audit") or {}).get("crap", {}).get("hotspots") or []
    if crap_rows:
        hotspot = crap_rows[0]
        lines.append(
            f"- `{hotspot['symbol']}` CRAP {hotspot['crap']:.1f} with complexity {hotspot['complexity']}. "
            "Above 30, add tests or split the function."
        )
    lines.append("")
    lines.append("Concrete tests to write:")
    lines.append("")
    actionable = [gap for gap in analysis.gaps if gap.symbol][:8]
    if not actionable:
        lines.append("- No symbol-level gaps. If the gate is still short of production-ready, raise branch coverage on the hotspots above.")
    for gap in actionable:
        lines.append(f"- `{gap.symbol}` ({gap.severity}): {gap.suggestion}")
    if analysis.project.test_runner:
        lines.append("")
        lines.append(
            "Re-run after editing tests: `recoverage run . --no-llm --threshold merge-ready`"
        )
    return "\n".join(lines)


def _scorecard(audit: dict) -> str:
    rows = ["| Dimension | Value | Threshold | Status |", "| --- | --- | --- | --- |"]
    for row in audit.get("scorecard") or []:
        rows.append(f"| {row['dimension']} | {row['value']} | {row['threshold']} | {row['status']} |")
    if len(rows) == 2:
        rows.append("| — | n/a | — | n/a |")
    return "\n".join(rows)


def _crap_table(audit: dict) -> str:
    crap = audit.get("crap") or {}
    lines = [
        crap.get("note") or "CRAP was not computed.",
        "",
        "| Function | Complexity | Coverage | CRAP |",
        "| --- | --- | --- | --- |",
    ]
    for row in (crap.get("rows") or [])[:8]:
        coverage = "n/a" if row.get("coverage") is None else f"{row['coverage']:.0%}"
        lines.append(f"| `{row['symbol']}` | {row['complexity']} | {coverage} | {row['crap']:.1f} |")
    if len(lines) == 4:
        lines.append("| — | — | — | — |")
    return "\n".join(lines)


def _assertion_note(audit: dict) -> str:
    assertions = audit.get("assertions") or {}
    authenticity = audit.get("authenticity") or {}
    flakiness = audit.get("flakiness") or {}
    phantoms = authenticity.get("phantoms") or []
    phantom_text = ", ".join(f"`{item['module']}`" for item in phantoms[:6]) or "none"
    return "\n".join(
        [
            assertions.get("note") or "Assertion strength was not computed.",
            "",
            f"Vacuous or tautological assertions: {len(assertions.get('vacuous') or [])}. "
            f"Assertion roulette: {assertions.get('assertion_roulette', 0)}. "
            f"Magic-number asserts: {assertions.get('magic_numbers', 0)}. "
            f"AAA interleaving: {assertions.get('aaa_violations', 0)}.",
            "",
            authenticity.get("note") or "Dependency authenticity was not computed.",
            "",
            f"Phantom imports: {phantom_text}.",
            "",
            flakiness.get("note") or "Flakiness risk was not computed.",
        ]
    )


def _pct(value: float | None) -> str:
    if value is None:
        return "not measured"
    return f"{value:.1f}%"


def _badge(gate: str) -> str:
    return {
        "production-ready": "PRODUCTION READY",
        "merge-ready": "MERGEABLE",
        "needs-review": "NEEDS REVIEW",
        "blocked": "NOT MERGEABLE",
    }[gate]


def _analytics_sections(analysis: Analysis) -> str:
    analytics = analysis.analytics or {}
    mutation = analytics.get("mutation") or {}
    prompt = analytics.get("prompt") or {}
    blast = analytics.get("blast") or {}
    timing = analytics.get("timing") or {}
    pbt = analytics.get("pbt") or {}
    graph = analytics.get("graph") or {}
    rows = ["| Symbol | Trials | Passed | Failed |", "| --- | --- | --- | --- |"]
    for row in pbt.get("properties") or []:
        rows.append(
            f"| `{row.get('symbol')}` | {row.get('trials')} | {row.get('passed')} | {row.get('failed')} |"
        )
    if len(rows) == 2:
        rows.append("| — | 0 | 0 | 0 |")
    communities = graph.get("communities") or []
    audit = analytics.get("audit") or {}
    return "\n".join(
        [
            mutation.get("note") or "Mutation testing did not run.",
            "",
            "## Authenticity scorecard",
            "",
            audit.get("note") or "Authenticity measurements were not computed.",
            "",
            _scorecard(audit),
            "",
            _crap_table(audit),
            "",
            _assertion_note(audit),
            "",
            "## Property-based testing",
            "",
            pbt.get("note") or "Property trials were not run.",
            "",
            "\n".join(rows),
            "",
            "## Prompt coverage",
            "",
            prompt.get("note") or "Prompt coverage was not computed.",
            "",
            "## Blast radius",
            "",
            blast.get("note") or "Blast radius was not computed.",
            "",
            f"Union coverage: {_pct(blast.get('union_coverage'))}.",
            "",
            "## Execution time",
            "",
            timing.get("note") or "Timing was not measured.",
            "",
            "## Code graph",
            "",
            f"Tree-sitter index: {'yes' if graph.get('tree_sitter') else 'no'}. "
            f"Entities: {len(graph.get('entities') or [])}. Communities: {len(communities)}.",
        ]
    )

