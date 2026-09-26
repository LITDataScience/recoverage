"""One projection of an Analysis. Markdown, HTML, and the PDF all read this."""

from __future__ import annotations

from dataclasses import dataclass

from recoverage.models import SEVERITY_ORDER, Analysis
from recoverage.score import RUBRIC_MD, explain_gate


@dataclass(frozen=True)
class CoverageRow:
    metric: str
    value: str


@dataclass(frozen=True)
class FactorRow:
    title: str
    earned: float
    maximum: float
    detail: str
    heuristic: bool


@dataclass(frozen=True)
class ModuleBar:
    name: str
    line_percent: float | None


@dataclass(frozen=True)
class HotspotRow:
    qualname: str
    file: str
    risk_score: float
    coverage_ratio: float | None
    risk_tags: tuple[str, ...]


@dataclass(frozen=True)
class FindingRow:
    id: str
    severity: str
    kind: str
    title: str
    why: str
    file: str
    symbol: str | None
    suggestion: str
    heuristic: bool
    llm_enriched: bool


@dataclass(frozen=True)
class FileRow:
    path: str
    statements: int
    covered: int
    line_percent: float | None
    functions: int
    gaps: int
    worst_gap: str | None


@dataclass(frozen=True)
class PropertyRow:
    symbol: str
    trials: int
    passed: int
    failed: int


@dataclass(frozen=True)
class AuditRow:
    dimension: str
    value: str
    threshold: str
    status: str


@dataclass(frozen=True)
class ReportView:
    score: float
    gate: str
    badge: str
    badge_color: str
    gate_sentence: str
    project_name: str
    language: str
    test_runner: str
    coverage_tool: str
    llm: str
    generated_at: str
    measured: bool
    mutation_ran: bool
    line_percent: float | None
    branch_percent: float | None
    coverage_rows: tuple[CoverageRow, ...]
    factors: tuple[FactorRow, ...]
    modules: tuple[ModuleBar, ...]
    hotspots: tuple[HotspotRow, ...]
    severity_counts: dict[str, int]
    findings: tuple[FindingRow, ...]
    files: tuple[FileRow, ...]
    notes: tuple[str, ...]
    suggestions: tuple[str, ...]
    rubric: str
    mutation_note: str
    prompt_note: str
    blast_note: str
    timing_note: str
    pbt_note: str
    pbt_rows: tuple[PropertyRow, ...]
    audit_note: str
    audit_rows: tuple[AuditRow, ...]
    crap_rows: tuple[dict, ...]
    assertion_note: str
    tree_sitter: bool
    entity_count: int
    community_count: int
    blast_union: float | None


_BADGE = {
    "production-ready": ("PRODUCTION READY", "#1e7a46"),
    "merge-ready": ("MERGEABLE", "#1f4e79"),
    "needs-review": ("NEEDS REVIEW", "#c47b00"),
    "blocked": ("NOT MERGEABLE", "#9b2335"),
}


def build_view(analysis: Analysis) -> ReportView:
    coverage = analysis.coverage
    badge, color = _BADGE[analysis.score.gate]
    analytics = analysis.analytics or {}
    audit = analytics.get("audit") or {}
    graph = analytics.get("graph") or {}
    blast = analytics.get("blast") or {}
    return ReportView(
        score=analysis.score.score,
        gate=analysis.score.gate,
        badge=badge,
        badge_color=color,
        gate_sentence=explain_gate(
            analysis.score.gate,
            score=analysis.score.score,
            runner=bool(analysis.project.test_runner),
            measured=coverage.measured,
            line=coverage.line_percent,
            critical=sum(1 for gap in analysis.gaps if gap.severity == "critical"),
            tests_exit_code=coverage.tests_exit_code,
        ),
        project_name=_project_name(analysis.project.root),
        language=analysis.project.primary_language,
        test_runner=analysis.project.test_runner or "none",
        coverage_tool=coverage.tool,
        llm=analysis.llm,
        generated_at=analysis.generated_at,
        measured=coverage.measured,
        mutation_ran=analysis.score.mutation_testing_ran,
        line_percent=coverage.line_percent,
        branch_percent=coverage.branch_percent,
        coverage_rows=_coverage_rows(analysis),
        factors=tuple(
            FactorRow(factor.title, factor.earned, factor.maximum, factor.detail, factor.heuristic)
            for factor in analysis.score.factors
        ),
        modules=tuple(ModuleBar(item.name, item.line_percent) for item in analysis.modules),
        hotspots=tuple(
            HotspotRow(item.qualname, item.file, item.risk_score, item.coverage_ratio, tuple(item.risk_tags))
            for item in analysis.hotspots
        ),
        severity_counts=_severity_counts(analysis),
        findings=_findings(analysis),
        files=_files(analysis),
        notes=tuple(analysis.project.notes),
        suggestions=tuple(_suggestions(analysis)),
        rubric=RUBRIC_MD.strip(),
        mutation_note=(analytics.get("mutation") or {}).get("note") or "Mutation testing did not run.",
        prompt_note=(analytics.get("prompt") or {}).get("note") or "Prompt coverage was not computed.",
        blast_note=blast.get("note") or "Blast radius was not computed.",
        timing_note=(analytics.get("timing") or {}).get("note") or "Timing was not measured.",
        pbt_note=(analytics.get("pbt") or {}).get("note") or "Property trials were not run.",
        pbt_rows=tuple(
            PropertyRow(
                str(row.get("symbol") or ""),
                int(row.get("trials") or 0),
                int(row.get("passed") or 0),
                int(row.get("failed") or 0),
            )
            for row in (analytics.get("pbt") or {}).get("properties") or []
        ),
        audit_note=audit.get("note") or "Authenticity measurements were not computed.",
        audit_rows=tuple(
            AuditRow(str(row.get("dimension")), str(row.get("value")), str(row.get("threshold")), str(row.get("status")))
            for row in audit.get("scorecard") or []
        ),
        crap_rows=tuple((audit.get("crap") or {}).get("rows") or [])[:8],
        assertion_note=_assertion_note(audit),
        tree_sitter=bool(graph.get("tree_sitter")),
        entity_count=len(graph.get("entities") or []),
        community_count=len(graph.get("communities") or []),
        blast_union=blast.get("union_coverage"),
    )


def _project_name(root: str) -> str:
    from pathlib import Path

    path = Path(root)
    return path.name if path.is_absolute() else root


def _pct(value: float | None) -> str:
    if value is None:
        return "not measured"
    return f"{value:.1f}%"


def _coverage_rows(analysis: Analysis) -> tuple[CoverageRow, ...]:
    coverage = analysis.coverage
    exit_code = "n/a" if coverage.tests_exit_code is None else str(coverage.tests_exit_code)
    return (
        CoverageRow("Project statement coverage", _pct(coverage.line_percent)),
        CoverageRow("Tool percent_covered", _pct(coverage.tool_line_percent)),
        CoverageRow("Branch coverage", _pct(coverage.branch_percent)),
        CoverageRow("Branch figure is runtime-tool-only", "yes" if coverage.branch_is_tool else "no"),
        CoverageRow("Tool", coverage.tool),
        CoverageRow("Measured", "yes" if coverage.measured else "no"),
        CoverageRow("Test exit code", exit_code),
    )


def _severity_counts(analysis: Analysis) -> dict[str, int]:
    counts = {name: 0 for name in ("critical", "high", "medium", "low")}
    for gap in analysis.gaps:
        if gap.severity in counts:
            counts[gap.severity] += 1
    return counts


def _findings(analysis: Analysis) -> tuple[FindingRow, ...]:
    ordered = sorted(analysis.gaps, key=lambda gap: (SEVERITY_ORDER.get(gap.severity, 9), gap.file, gap.symbol or "", gap.kind))
    return tuple(
        FindingRow(
            gap.id,
            gap.severity,
            gap.kind,
            gap.title,
            gap.why,
            gap.file,
            gap.symbol,
            gap.suggestion,
            gap.heuristic,
            gap.llm_enriched,
        )
        for gap in ordered
    )


def _files(analysis: Analysis) -> tuple[FileRow, ...]:
    buckets: dict[str, dict] = {}

    def bucket(path: str) -> dict:
        return buckets.setdefault(path, {"statements": 0, "covered": 0, "functions": 0, "gaps": 0, "worst": None, "rank": 9})

    for function in analysis.functions:
        item = bucket(function.spec.file)
        item["statements"] += function.executable_lines
        item["covered"] += function.covered_lines
        item["functions"] += 1
    for gap in analysis.gaps:
        if not gap.file:
            continue
        item = bucket(gap.file)
        item["gaps"] += 1
        rank = SEVERITY_ORDER.get(gap.severity, 9)
        if rank < item["rank"]:
            item["rank"] = rank
            item["worst"] = gap.severity
    rows = []
    for path in sorted(buckets):
        item = buckets[path]
        percent = None
        if item["statements"]:
            percent = round(100.0 * item["covered"] / item["statements"], 1)
        rows.append(
            FileRow(path, item["statements"], item["covered"], percent, item["functions"], item["gaps"], item["worst"])
        )
    return tuple(rows)


def _suggestions(analysis: Analysis) -> list[str]:
    lines = [
        "Read the findings from the top. Critical and high items are the ones that move the gate.",
        "`recoverage generate` keeps a draft only after a temp-copy compile and 5 passing runs, and only if it adds covered lines or kills a mutant the current suite left alive.",
        "Recoverage will not delete or overwrite an existing test file.",
        "Prompt coverage is a lexical entropy proxy unless an attention model was queried. The report names which one ran.",
        "Mutation counts come from temp-copy mutants. If that section says mutation did not run, it did not.",
    ]
    if not analysis.coverage.measured:
        if analysis.project.primary_language == "python":
            lines.append("Runtime coverage did not run. Install coverage and make the tests import the package under test.")
        elif analysis.project.primary_language in {"javascript", "typescript"}:
            lines.append("Runtime coverage did not run. Install c8 or nyc locally, then re-run. Recoverage will not npm install for you.")
        else:
            lines.append("This language has static structure analysis only. There is no runtime coverage number to chase yet.")
    crap_rows = ((analysis.analytics or {}).get("audit") or {}).get("crap", {}).get("hotspots") or []
    if crap_rows:
        hotspot = crap_rows[0]
        lines.append(
            f"`{hotspot['symbol']}` CRAP {hotspot['crap']:.1f} with complexity {hotspot['complexity']}. Above 30, add tests or split the function."
        )
    symbol_lines = 0
    for gap in analysis.gaps:
        if not gap.symbol:
            continue
        lines.append(f"`{gap.symbol}` ({gap.severity}): {gap.suggestion}")
        symbol_lines += 1
        if symbol_lines >= 8:
            break
    if analysis.project.test_runner:
        lines.append("Re-run after editing tests: `recoverage run . --no-llm --threshold merge-ready`")
    return lines


def _assertion_note(audit: dict) -> str:
    assertions = audit.get("assertions") or {}
    authenticity = audit.get("authenticity") or {}
    flakiness = audit.get("flakiness") or {}
    phantoms = authenticity.get("phantoms") or []
    phantom_text = ", ".join(f"`{item['module']}`" for item in phantoms[:6]) or "none"
    parts = [
        assertions.get("note") or "Assertion strength was not computed.",
        (
            f"Vacuous or tautological assertions: {len(assertions.get('vacuous') or [])}. "
            f"Assertion roulette: {assertions.get('assertion_roulette', 0)}. "
            f"Magic-number asserts: {assertions.get('magic_numbers', 0)}. "
            f"AAA interleaving: {assertions.get('aaa_violations', 0)}."
        ),
        authenticity.get("note") or "Dependency authenticity was not computed.",
        f"Phantom imports: {phantom_text}.",
        flakiness.get("note") or "Flakiness risk was not computed.",
    ]
    return " ".join(parts)
