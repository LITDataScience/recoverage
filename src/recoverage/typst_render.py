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
    from recoverage.report import _gate_sentence

    badge, color = _BADGE[analysis.score.gate]
    analytics = analysis.analytics or {}
    pbt = analytics.get("pbt") or {}
    counts = {name: 0 for name in _SEVERITY_COLORS}
    for gap in analysis.gaps:
        if gap.severity in counts:
            counts[gap.severity] += 1
    suggestions = _suggestions(analysis)
    return {
        "score": analysis.score.score,
        "gate": analysis.score.gate,
        "blurb": _gate_sentence(analysis),
        "badge": badge,
        "badge_color": color,
        "factors": [
            {
                "title": factor.title,
                "earned": factor.earned,
                "maximum": factor.maximum,
                "detail": factor.detail,
            }
            for factor in analysis.score.factors
        ],
        "modules": [
            {"name": item.name, "line_percent": item.line_percent}
            for item in analysis.modules
        ],
        "severities": [
            {"name": name, "count": counts[name], "color": _SEVERITY_COLORS[name]}
            for name in ("critical", "high", "medium", "low")
        ],
        "pbt": {
            "note": pbt.get("note") or "Property trials were not run.",
            "rows": [
                {
                    "symbol": row.get("symbol", ""),
                    "trials": row.get("trials", 0),
                    "passed": row.get("passed", 0),
                    "failed": row.get("failed", 0),
                }
                for row in pbt.get("properties") or []
            ],
        },
        "mutation": (analytics.get("mutation") or {}).get("note") or "Mutation testing was not run.",
        "prompt": (analytics.get("prompt") or {}).get("note") or "Prompt coverage was not computed.",
        "blast": (analytics.get("blast") or {}).get("note") or "Blast radius was not computed.",
        "timing": (analytics.get("timing") or {}).get("note") or "Timing was not measured.",
        "audit": {
            "note": (analytics.get("audit") or {}).get("note") or "Authenticity measurements were not computed.",
            "rows": (analytics.get("audit") or {}).get("scorecard") or [],
        },
        "suggestions": suggestions,
        "rubric": RUBRIC_MD.strip(),
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
    raise RuntimeError("typst CLI is not on PATH. Install it from https://github.com/typst/typst/releases")
