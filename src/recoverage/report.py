"""Markdown report. The PDF is compiled from the same analysis by Typst."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from recoverage.models import Analysis
from recoverage.score import RUBRIC_MD, explain_gate
from recoverage.typst_render import TypstMissing, write_typst_pdf

_GATE_HEX = {
    "blocked": "#9B2335",
    "needs-review": "#C47B00",
    "merge-ready": "#1F4E79",
    "production-ready": "#1E7A46",
}


def build_markdown(analysis: Analysis) -> str:
    from recoverage.reportview import build_view

    view = build_view(analysis)
    score = analysis.score
    lines = [
        "# Recoverage report",
        "",
        f"**Merge Readiness Score: {view.score:.1f} / 100**  ",
        f"**Gate: `{view.gate}`**  ",
        f"**Badge: `{view.badge}`**",
        "",
        view.gate_sentence,
        "",
        f"Project: `{view.project_name}`  ",
        f"Language: {view.language}  ",
        f"Test runner: {view.test_runner}  ",
        f"Coverage tool: {view.coverage_tool}  ",
        f"LLM: {view.llm}  ",
        f"Generated: {view.generated_at}",
        "",
        *_project_notes(analysis),
        f"<!-- recoverage:score={score.score:.1f};gate={score.gate};mutation={'true' if score.mutation_testing_ran else 'false'} -->",
        "",
        "## Overview",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Statement coverage | {_pct(view.line_percent)} |",
        f"| Branch coverage | {_pct(view.branch_percent)} |",
        f"| Gaps | {sum(view.severity_counts.values())} |",
        f"| Mutation ran | {'yes' if view.mutation_ran else 'no'} |",
        "",
        "## Coverage stats",
        "",
        _coverage_table(view),
        "",
        "## Score factors",
        "",
        _factor_table(view),
        "",
        "## Coverage by package",
        "",
        "{{chart:coverage_by_package}}",
        "",
        "## Gap severity",
        "",
        "{{chart:gap_severity}}",
        "",
        _analytics_sections(view),
        "",
        "## Risk hotspots",
        "",
        "{{chart:risk_hotspots}}",
        "",
        _hotspot_table(view),
        "",
        "## Files",
        "",
        _file_table(view),
        "",
        "## Findings",
        "",
        _findings(view),
        "",
        "## Suggestions",
        "",
        "\n".join(f"- {line}" for line in view.suggestions),
        "",
        view.rubric,
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
    try:
        write_typst_pdf(analysis, output_dir)
    except TypstMissing as exc:
        if pdf_path.is_file():
            pdf_path.unlink()
        print(f"recoverage: {exc} Markdown and HTML were written.", file=sys.stderr)
    return md_path, pdf_path, html_path


def _project_notes(analysis: Analysis) -> list[str]:
    notes = list(analysis.project.notes)
    if not notes:
        return []
    return ["", *[f"- {note}" for note in notes], ""]


def _md(value: str) -> str:
    """Keep gap text from becoming a Markdown link or image."""
    escaped = value.replace("\\", "\\\\")
    for char in ("`", "*", "_", "[", "]", "(", ")", "<", ">", "!", "#"):
        escaped = escaped.replace(char, "\\" + char)
    return escaped.replace("\n", " ")


def _gate_sentence(analysis: Analysis) -> str:
    coverage = analysis.coverage
    return explain_gate(
        analysis.score.gate,
        score=analysis.score.score,
        runner=bool(analysis.project.test_runner),
        measured=coverage.measured,
        line=coverage.line_percent,
        critical=sum(1 for gap in analysis.gaps if gap.severity == "critical"),
        tests_exit_code=coverage.tests_exit_code,
    )


def _markdown_with_images(markdown: str, charts: dict[str, Path], md_path: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        chart = charts.get(key)
        if chart is None:
            return ""
        relative = chart.relative_to(md_path.parent).as_posix()
        return f"![{key.replace('_', ' ')}]({relative})"

    return re.sub(r"\{\{chart:([a-z0-9_]+)\}\}", replace, markdown)


def _coverage_table(view) -> str:
    rows = ["| Metric | Value |", "| --- | --- |"]
    rows.extend(f"| {row.metric} | {row.value} |" for row in view.coverage_rows)
    return "\n".join(rows)


def _factor_table(view) -> str:
    rows = ["| Factor | Earned | Max | Heuristic | Detail |", "| --- | --- | --- | --- | --- |"]
    for factor in view.factors:
        detail = factor.detail.replace("|", "/")
        rows.append(
            f"| {factor.title} | {factor.earned:.2f} | {factor.maximum:.0f} | "
            f"{'yes' if factor.heuristic else 'no'} | {detail} |"
        )
    return "\n".join(rows)


def _hotspot_table(view) -> str:
    if not view.hotspots:
        return "No hotspots."
    rows = ["| Function | File | Risk | Coverage | Tags |", "| --- | --- | --- | --- | --- |"]
    for spot in view.hotspots:
        coverage = "n/a" if spot.coverage_ratio is None else f"{spot.coverage_ratio:.0%}"
        tags = ", ".join(spot.risk_tags) or "—"
        rows.append(f"| `{spot.qualname}` | `{spot.file}` | {spot.risk_score:.2f} | {coverage} | {tags} |")
    return "\n".join(rows)


def _file_table(view) -> str:
    if not view.files:
        return "No files."
    rows = ["| File | Statements | Coverage | Functions | Gaps | Worst |", "| --- | --- | --- | --- | --- | --- |"]
    for row in view.files:
        percent = "not measured" if row.line_percent is None else f"{row.line_percent:.1f}%"
        rows.append(
            f"| `{row.path}` | {row.statements} | {percent} | {row.functions} | {row.gaps} | {row.worst_gap or '—'} |"
        )
    return "\n".join(rows)


def _findings(view) -> str:
    if not view.findings:
        return "No gaps recorded."
    blocks = []
    current = None
    for gap in view.findings:
        if gap.severity != current:
            current = gap.severity
            blocks.append(f"### {current}")
        where = f"`{gap.file}`" if gap.file else "project"
        symbol = f" `{gap.symbol}`" if gap.symbol else ""
        heuristic = " Heuristic." if gap.heuristic else ""
        llm = " LLM-enriched." if gap.llm_enriched else ""
        blocks.append(
            f"#### {gap.id} · {_md(gap.title)}\n\n"
            f"{where}{symbol}. Kind: `{gap.kind}`.{heuristic}{llm}\n\n"
            f"{_md(gap.why)}\n\n"
            f"Suggestion: {_md(gap.suggestion)}"
        )
    return "\n\n".join(blocks)


def _suggestions(analysis: Analysis) -> str:
    """Developer-facing next actions. Not a restatement of the score."""
    lines = [
        "Read the findings from the top. Critical and high items are the ones that move the gate.",
        "",
        "- `recoverage generate` keeps a draft only after a temp-copy compile and 5 passing runs, and only if it adds covered lines or kills a mutant the current suite left alive. It does not lock in observed return values.",
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


def _display_root(root: str) -> str:
    path = Path(root)
    return path.name if path.is_absolute() else root


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


def _analytics_sections(view) -> str:
    rows = ["| Symbol | Trials | Passed | Failed |", "| --- | --- | --- | --- |"]
    for row in view.pbt_rows:
        rows.append(f"| `{row.symbol}` | {row.trials} | {row.passed} | {row.failed} |")
    if len(rows) == 2:
        rows.append("| — | 0 | 0 | 0 |")
    audit_rows = ["| Dimension | Value | Threshold | Status |", "| --- | --- | --- | --- |"]
    for row in view.audit_rows:
        audit_rows.append(f"| {row.dimension} | {row.value} | {row.threshold} | {row.status} |")
    if len(audit_rows) == 2:
        audit_rows.append("| — | n/a | — | n/a |")
    return "\n".join(
        [
            view.mutation_note,
            "",
            "## Authenticity scorecard",
            "",
            view.audit_note,
            "",
            "\n".join(audit_rows),
            "",
            view.assertion_note,
            "",
            "## Property-based testing",
            "",
            view.pbt_note,
            "",
            "\n".join(rows),
            "",
            "## Prompt coverage",
            "",
            view.prompt_note,
            "",
            "## Blast radius",
            "",
            view.blast_note,
            "",
            f"Union coverage: {_pct(view.blast_union)}.",
            "",
            "## Execution time",
            "",
            view.timing_note,
            "",
            "## Code graph",
            "",
            f"Tree-sitter index: {'yes' if view.tree_sitter else 'no'}. "
            f"Entities: {view.entity_count}. Communities: {view.community_count}.",
        ]
    )

