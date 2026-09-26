"""Compile the Typst template from one JSON document."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from recoverage.models import Analysis
from recoverage.score import RUBRIC_MD

_SEVERITY_COLORS = {
    "critical": "#9b2335",
    "high": "#d35400",
    "medium": "#c47b00",
    "low": "#2e6b9a",
}
_BADGE = {
    "production-ready": ("PRODUCTION READY", "#1e7a46"),
    "merge-ready": ("MERGEABLE", "#1f4e79"),
    "needs-review": ("NEEDS REVIEW", "#c47b00"),
    "blocked": ("NOT MERGEABLE", "#9b2335"),
}


class TypstMissing(RuntimeError):
    """The Typst binary is absent. Markdown and HTML are still valid output."""


def write_typst_pdf(analysis: Analysis, output_dir: Path) -> Path:
    typst = _find_typst()
    output_dir.mkdir(parents=True, exist_ok=True)
    template = Path(__file__).with_name("templates") / "report.typ"
    if not template.is_file():
        raise FileNotFoundError(f"missing Typst template: {template}")
    view = _view(analysis)
    (output_dir / "mrs.json").write_text(json.dumps(view), encoding="utf-8")
    (output_dir / "report.typ").write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    pdf_path = output_dir / "report.pdf"
    completed = subprocess.run(
        [typst, "compile", "report.typ", "report.pdf"],
        cwd=output_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0 or not pdf_path.is_file():
        detail = (completed.stderr or completed.stdout or "typst produced no pdf").strip()
        raise RuntimeError(detail)
    return pdf_path


def _view(analysis: Analysis) -> dict:
    from recoverage.reportview import build_view

    view = build_view(analysis)
    shown = view.files[:60]
    return {
        "score": view.score,
        "gate": view.gate,
        "blurb": view.gate_sentence,
        "badge": view.badge,
        "badge_color": view.badge_color,
        "project": view.project_name,
        "line": "not measured" if view.line_percent is None else f"{view.line_percent:.1f}%",
        "branch": "not measured" if view.branch_percent is None else f"{view.branch_percent:.1f}%",
        "gap_count": sum(view.severity_counts.values()),
        "mutation_ran": "yes" if view.mutation_ran else "no",
        "factors": [
            {"title": factor.title, "earned": factor.earned, "maximum": factor.maximum, "detail": factor.detail}
            for factor in view.factors
        ],
        "modules": [{"name": item.name, "line_percent": item.line_percent} for item in view.modules],
        "severities": [
            {"name": name, "count": view.severity_counts[name], "color": _SEVERITY_COLORS[name]}
            for name in ("critical", "high", "medium", "low")
        ],
        "files": [
            {
                "path": row.path,
                "statements": row.statements,
                "coverage": "not measured" if row.line_percent is None else f"{row.line_percent:.1f}%",
                "gaps": row.gaps,
            }
            for row in shown
        ],
        "files_omitted": max(0, len(view.files) - len(shown)),
        "findings": [
            {
                "id": gap.id,
                "severity": gap.severity,
                "title": gap.title,
                "where": gap.file or "project",
                "why": gap.why,
            }
            for gap in view.findings
        ],
        "pbt": {
            "note": view.pbt_note,
            "rows": [
                {"symbol": row.symbol, "trials": row.trials, "passed": row.passed, "failed": row.failed}
                for row in view.pbt_rows
            ],
        },
        "mutation": view.mutation_note,
        "prompt": view.prompt_note,
        "blast": view.blast_note,
        "timing": view.timing_note,
        "audit": {"note": view.audit_note, "rows": [row.__dict__ for row in view.audit_rows]},
        "suggestions": list(view.suggestions),
        "rubric": view.rubric,
    }


def _suggestions(analysis: Analysis) -> list[str]:
    lines = []
    ranked = sorted((analysis.analytics or {}).get("graph", {}).get("pagerank") or [], key=lambda item: -item.get("pagerank", 0))
    if ranked:
        top = ranked[0]
        lines.append(
            f"{top['symbol']} has PageRank {top['pagerank']:.4f} in community {top.get('community')}. "
            "Test that symbol against its graph neighbors instead of an isolated file dump."
        )
    crap_rows = ((analysis.analytics or {}).get("audit") or {}).get("crap", {}).get("hotspots") or []
    if crap_rows:
        hotspot = crap_rows[0]
        lines.append(
            f"{hotspot['symbol']} has CRAP {hotspot['crap']:.1f} "
            f"(complexity {hotspot['complexity']}). Above 30, add tests or split the function."
        )
    for gap in analysis.gaps:
        if gap.symbol and gap.severity in {"critical", "high"}:
            lines.append(f"{gap.symbol}: {gap.suggestion}")
        if len(lines) >= 8:
            break
    if not lines:
        lines.append("No high-centrality symbol or critical gap was recorded.")
    return lines


def _find_typst() -> str:
    found = shutil.which("typst")
    if found:
        return found
    candidate = Path.home() / ".local" / "bin" / "typst"
    if candidate.is_file():
        return str(candidate)
    raise TypstMissing("typst CLI is not on PATH. Install it from https://github.com/typst/typst/releases.")
