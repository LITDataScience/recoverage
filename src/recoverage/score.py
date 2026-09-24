"""Merge Readiness Score. Weights are the PRD's, not a disguised line-coverage percent."""

from __future__ import annotations

from pathlib import Path

from recoverage.models import CoverageResult, Gap, MappedFunction, ProjectProfile, ScoreFactor, ScoreResult

RUBRIC_MD = Path(__file__).with_name("RUBRIC.md").read_text(encoding="utf-8")

_GATE_BLURB = {
    "merge-ready": "Mergeable under this rubric. The production-ready badge still requires a Merge Readiness Score of at least 85.",
    "production-ready": "Production ready under this rubric: Merge Readiness Score at least 85, measured coverage, and no critical gap. This is not a security audit.",
}


def explain_gate(
    gate: str,
    *,
    score: float,
    runner: bool,
    measured: bool,
    line: float | None,
    critical: int,
) -> str:
    """Say why this gate was chosen. Do not mention a cause that did not happen."""
    if gate == "blocked":
        reasons: list[str] = []
        if not runner:
            reasons.append("there is no test runner")
        if measured and line is not None and line < 20:
            reasons.append(f"measured statement coverage is {line:.1f}%, under 20%")
        if score < 40:
            reasons.append(f"the Merge Readiness Score is {score:.1f}, under 40")
        if not reasons:
            reasons.append("the blocked rule matched")
        return "Not mergeable. " + _join_reasons(reasons) + "."
    if gate == "needs-review":
        reasons = []
        if not measured:
            reasons.append("runtime coverage was not measured")
        if score < 70:
            reasons.append(f"the Merge Readiness Score is {score:.1f}, below the merge bar of 70")
        if measured and line is not None and line < 60:
            reasons.append(f"statement coverage is {line:.1f}%, under 60%")
        if critical:
            reasons.append(f"{critical} critical gap" + ("s remain open" if critical != 1 else " remains open"))
        if not reasons:
            reasons.append("the merge bar is not met")
        return "Needs review. " + _join_reasons(reasons) + "."
    return _GATE_BLURB[gate]


def _join_reasons(reasons: list[str]) -> str:
    head = reasons[0][0].upper() + reasons[0][1:]
    if len(reasons) == 1:
        return head
    if len(reasons) == 2:
        return f"{head}, and {reasons[1]}"
    return f"{head}, {', '.join(reasons[1:-1])}, and {reasons[-1]}"


def score_project(
    profile: ProjectProfile,
    coverage: CoverageResult,
    functions: list[MappedFunction],
    gaps: list[Gap],
    analytics: dict | None = None,
) -> ScoreResult:
    del functions
    analytics = analytics or {}
    factors = [
        _structural(coverage),
        _pbt(analytics.get("pbt") or {}),
        _prompt(analytics.get("prompt") or {}),
        _blast(analytics.get("blast") or {}, coverage),
        _timing(analytics.get("timing") or {}),
    ]
    total = sum(factor.earned for factor in factors)
    if profile.flake_markers:
        total = max(0.0, total - 2.0)
    total = round(total, 1)
    critical = sum(1 for gap in gaps if gap.severity == "critical")
    gate = decide_gate(
        total,
        runner=bool(profile.test_runner),
        measured=coverage.measured,
        line=coverage.line_percent,
        critical=critical,
    )
    mutation = analytics.get("mutation") or {}
    notes = [
        explain_gate(
            gate,
            score=total,
            runner=bool(profile.test_runner),
            measured=coverage.measured,
            line=coverage.line_percent,
            critical=critical,
        ),
        mutation.get("note") or "Mutation testing did not run.",
    ]
    if profile.flake_markers:
        notes.append(
            "Subtracted 2 because flake markers were found by a static scan. Flakiness of the existing suite was not reproduced."
        )
    if coverage.notes:
        notes.extend(coverage.notes[:4])
    return ScoreResult(
        score=total,
        gate=gate,
        factors=factors,
        mutation_testing_ran=bool(mutation.get("ran")),
        notes=notes,
    )


def decide_gate(
    score: float,
    *,
    runner: bool,
    measured: bool,
    line: float | None,
    critical: int,
    threshold: float = 85,
) -> str:
    if not runner or score < 40 or (measured and line is not None and line < 20):
        return "blocked"
    if not measured:
        return "needs-review"
    if score >= threshold and line is not None and line >= 60 and critical == 0:
        return "production-ready"
    if score >= 70 and line is not None and line >= 60 and critical == 0:
        return "merge-ready"
    return "needs-review"


def meets_threshold(result: ScoreResult, threshold: str | None) -> bool:
    if threshold is None or threshold == "":
        return True
    from recoverage.models import GATE_RANK, GATES

    if threshold in GATES:
        return GATE_RANK[result.gate] >= GATE_RANK[threshold]
    return result.score >= float(threshold)


def _structural(coverage: CoverageResult) -> ScoreFactor:
    if not coverage.measured or coverage.line_percent is None:
        return ScoreFactor(
            id="structural",
            title="Structural coverage",
            earned=0.0,
            maximum=40.0,
            detail="Runtime coverage was not measured. These points are 0.",
            heuristic=False,
        )
    branch = 0.0 if coverage.branch_percent is None else coverage.branch_percent
    blended = 0.6 * coverage.line_percent + 0.4 * branch
    earned = round(40.0 * blended / 100.0, 2)
    detail = (
        f"Statement coverage {coverage.line_percent:.1f}% and branch coverage {branch:.1f}% "
        f"combine to {blended:.1f} before the 40-point weight."
    )
    if coverage.tool_line_percent is not None and abs(coverage.tool_line_percent - coverage.line_percent) > 0.2:
        detail += (
            f" Tool percent_covered is {coverage.tool_line_percent:.1f}% and is not used: "
            "branch mode blends arcs into that headline."
        )
    if not coverage.branch_is_tool:
        detail += " The branch figure mixes tool arcs with static decisions, so this factor is partly heuristic."
    return ScoreFactor(
        id="structural",
        title="Structural coverage",
        earned=earned,
        maximum=40.0,
        detail=detail,
        heuristic=not coverage.branch_is_tool,
    )


def _pbt(report: dict) -> ScoreFactor:
    if not report.get("ran"):
        return ScoreFactor(
            id="pbt",
            title="Property-based resilience",
            earned=0.0,
            maximum=25.0,
            detail=report.get("note") or "Property trials were not run.",
            heuristic=False,
        )
    trials = int(report.get("trials") or 0)
    passed = int(report.get("passed") or 0)
    ratio = 0.0 if trials == 0 else passed / trials
    return ScoreFactor(
        id="pbt",
        title="Property-based resilience",
        earned=round(25.0 * ratio, 2),
        maximum=25.0,
        detail=report.get("note") or f"{passed}/{trials} property trials held.",
        heuristic=False,
    )


def _prompt(report: dict) -> ScoreFactor:
    if not report.get("ran") or report.get("coverage") is None:
        return ScoreFactor(
            id="prompt",
            title="Prompt / semantic alignment",
            earned=0.0,
            maximum=15.0,
            detail=report.get("note") or "Prompt coverage was not computed.",
            heuristic=True,
        )
    coverage = float(report["coverage"])
    return ScoreFactor(
        id="prompt",
        title="Prompt / semantic alignment",
        earned=round(15.0 * coverage / 100.0, 2),
        maximum=15.0,
        detail=f"ΔH coverage {coverage:.1f}%. {report.get('note', '')}",
        heuristic=report.get("method") != "attention",
    )


def _blast(report: dict, coverage: CoverageResult) -> ScoreFactor:
    union = report.get("union_coverage")
    if union is None:
        union = coverage.line_percent if coverage.measured else None
    if union is None:
        return ScoreFactor(
            id="blast",
            title="Blast radius safety",
            earned=0.0,
            maximum=10.0,
            detail=report.get("note") or "Blast radius was not computed.",
            heuristic=True,
        )
    return ScoreFactor(
        id="blast",
        title="Blast radius safety",
        earned=round(10.0 * float(union) / 100.0, 2),
        maximum=10.0,
        detail=report.get("note") or f"Union coverage {float(union):.1f}%.",
        heuristic=not report.get("diff", False),
    )


def _timing(report: dict) -> ScoreFactor:
    if not report.get("ran"):
        return ScoreFactor(
            id="timing",
            title="Execution-time efficiency",
            earned=0.0,
            maximum=10.0,
            detail=report.get("note") or "Timing was not measured.",
            heuristic=False,
        )
    if report.get("regression"):
        return ScoreFactor(
            id="timing",
            title="Execution-time efficiency",
            earned=0.0,
            maximum=10.0,
            detail=report.get("note") or "A statistically slower input class was detected.",
            heuristic=False,
        )
    return ScoreFactor(
        id="timing",
        title="Execution-time efficiency",
        earned=10.0,
        maximum=10.0,
        detail=report.get("note") or "No significant slowdown.",
        heuristic=False,
    )
