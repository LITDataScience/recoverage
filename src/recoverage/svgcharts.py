"""Charts as SVG strings. No matplotlib, no network, deterministic."""

from __future__ import annotations

import html
from pathlib import Path

from recoverage.reportview import ReportView

_NAVY = "#1F4E79"
_TEAL = "#1F7A6B"
_AMBER = "#C47B00"
_RED = "#9B2335"
_BLUE = "#2E6B9A"
_GRAY = "#8A93A0"
_TRACK = "#E7E1D8"
_INK = "#1C1917"
_SEVERITY = {"critical": _RED, "high": "#D35400", "medium": _AMBER, "low": _BLUE}


def write_svgs(view: ReportView, output_dir: Path) -> dict[str, Path]:
    chart_dir = output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "score_gauge": chart_dir / "score_gauge.svg",
        "coverage_by_package": chart_dir / "coverage_by_package.svg",
        "risk_hotspots": chart_dir / "risk_hotspots.svg",
        "gap_severity": chart_dir / "gap_severity.svg",
    }
    paths["score_gauge"].write_text(score_gauge(view), encoding="utf-8")
    paths["coverage_by_package"].write_text(coverage_bars(view), encoding="utf-8")
    paths["risk_hotspots"].write_text(hotspot_bars(view), encoding="utf-8")
    paths["gap_severity"].write_text(severity_bars(view), encoding="utf-8")
    return paths


def score_gauge(view: ReportView) -> str:
    span = max(0.0, min(100.0, view.score))
    # Semicircle from west to east. The filled arc is the score.
    start = _point(100, 108, 72, 180)
    end = _point(100, 108, 72, 180 - 180 * span / 100)
    large = 1 if span > 50 else 0
    arc = ""
    if span > 0:
        arc = (
            f'<path d="M {start[0]:.2f} {start[1]:.2f} A 72 72 0 {large} 1 {end[0]:.2f} {end[1]:.2f}" '
            f'fill="none" stroke="{view.badge_color}" stroke-width="14" stroke-linecap="round"/>'
        )
    title = html.escape(f"Score {view.score:.1f} of 100, gate {view.gate}")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 130" role="img" aria-label="{title}">'
        f"<title>{title}</title>"
        '<path d="M 28 108 A 72 72 0 0 1 172 108" fill="none" stroke="#E7E1D8" stroke-width="14" stroke-linecap="round"/>'
        f"{arc}"
        f'<text x="100" y="96" text-anchor="middle" font-size="28" font-weight="700" fill="{_INK}" '
        f'font-family="Segoe UI, sans-serif">{view.score:.1f}</text>'
        f'<text x="100" y="116" text-anchor="middle" font-size="11" fill="#57534e" '
        f'font-family="Segoe UI, sans-serif">{html.escape(view.badge)}</text>'
        "</svg>"
    )


def coverage_bars(view: ReportView) -> str:
    rows = list(view.modules) or []
    if not rows:
        rows_drawn = [("no modules", None)]
    else:
        rows_drawn = [(item.name, item.line_percent) for item in rows]
    return _hbar(
        "Coverage by module",
        [(name, 0.0 if value is None else value, 100.0, _coverage_color(view.measured, value), _pct(value)) for name, value in rows_drawn],
        measured=view.measured,
    )


def hotspot_bars(view: ReportView) -> str:
    spots = list(view.hotspots[:8])
    if not spots:
        drawn = [("none", 0.0, 1.0, _GRAY, "0.00")]
    else:
        drawn = [
            (item.qualname, item.risk_score, 1.0, _risk_color(item.coverage_ratio), f"{item.risk_score:.2f}")
            for item in reversed(spots)
        ]
    return _hbar("Risk hotspots", drawn, measured=True)


def severity_bars(view: ReportView) -> str:
    order = ("critical", "high", "medium", "low")
    peak = max((view.severity_counts.get(name, 0) for name in order), default=0) or 1
    drawn = [
        (name, float(view.severity_counts.get(name, 0)), float(peak), _SEVERITY[name], str(view.severity_counts.get(name, 0)))
        for name in order
    ]
    return _hbar("Gap severity", drawn, measured=True)


def _coverage_color(measured: bool, value: float | None) -> str:
    if not measured or value is None:
        return _GRAY
    if value >= 80:
        return _TEAL
    if value >= 60:
        return _NAVY
    return _AMBER


def _risk_color(ratio: float | None) -> str:
    if ratio is None:
        return _GRAY
    if ratio >= 0.8:
        return _TEAL
    if ratio > 0:
        return _AMBER
    return _RED


def _pct(value: float | None) -> str:
    if value is None:
        return "not measured"
    return f"{value:.1f}%"


def _hbar(title: str, rows: list[tuple[str, float, float, str, str]], *, measured: bool) -> str:
    label_w = 168
    bar_w = 360
    row_h = 28
    height = 36 + row_h * len(rows)
    width = 640
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{html.escape(title)}">',
        f"<title>{html.escape(title)}</title>",
        f'<text x="8" y="18" font-size="13" font-weight="700" fill="{_NAVY}" font-family="Segoe UI, sans-serif">{html.escape(title)}</text>',
    ]
    for index, (name, value, scale, color, caption) in enumerate(rows):
        y = 32 + index * row_h
        width_px = 0 if scale <= 0 else max(0.0, min(bar_w, bar_w * value / scale))
        parts.append(
            f'<text x="8" y="{y + 14}" font-size="11" fill="{_INK}" font-family="Segoe UI, sans-serif">{html.escape(name)}</text>'
        )
        parts.append(f'<rect x="{label_w}" y="{y}" width="{bar_w}" height="16" rx="3" fill="{_TRACK}"/>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{width_px:.1f}" height="16" rx="3" fill="{color}"/>')
        parts.append(
            f'<text x="{label_w + bar_w + 8}" y="{y + 13}" font-size="11" fill="{_INK}" '
            f'font-family="Segoe UI, sans-serif">{html.escape(caption)}</text>'
        )
    if not measured:
        parts.append(
            f'<text x="{label_w + bar_w / 2}" y="{height - 6}" text-anchor="middle" font-size="12" fill="{_GRAY}" '
            f'font-family="Segoe UI, sans-serif">not measured</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _point(cx: float, cy: float, radius: float, degrees: float) -> tuple[float, float]:
    import math

    radians = math.radians(degrees)
    return cx + radius * math.cos(radians), cy - radius * math.sin(radians)
