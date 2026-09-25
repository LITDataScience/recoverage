"""Real matplotlib charts. No ASCII stand-ins."""

from __future__ import annotations

from pathlib import Path

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover - optional extra
    plt = None

from recoverage.models import Analysis

_NAVY = "#1F4E79"
_TEAL = "#1F7A6B"
_AMBER = "#C47B00"
_RED = "#9B2335"
_BLUE = "#2E6B9A"
_GRAY = "#8A93A0"
_SEVERITY_COLORS = {
    "critical": _RED,
    "high": "#D35400",
    "medium": _AMBER,
    "low": _BLUE,
}


def write_charts(analysis: Analysis, output_dir: Path) -> dict[str, Path]:
    if plt is None:
        return {}
    chart_dir = output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "coverage_by_package": chart_dir / "coverage_by_package.png",
        "risk_hotspots": chart_dir / "risk_hotspots.png",
        "gap_severity": chart_dir / "gap_severity.png",
    }
    _coverage_chart(analysis, paths["coverage_by_package"])
    _hotspot_chart(analysis, paths["risk_hotspots"])
    _severity_chart(analysis, paths["gap_severity"])
    return paths


def _coverage_chart(analysis: Analysis, path: Path) -> None:
    modules = analysis.modules or []
    labels = [item.name for item in modules] or ["(no modules)"]
    measured = analysis.coverage.measured
    values = [
        0 if item.line_percent is None else item.line_percent
        for item in modules
    ] or [0]
    figure, axis = plt.subplots(figsize=(8.2, 4.4))
    colors = [_TEAL if measured and value >= 80 else _NAVY if measured and value >= 60 else _AMBER if measured else _GRAY for value in values]
    axis.bar(labels, values, color=colors)
    axis.set_ylim(0, 100)
    axis.set_ylabel("Line coverage %")
    title = "Coverage by package / module"
    if not measured:
        title += " — runtime coverage was not measured"
    axis.set_title(title)
    axis.tick_params(axis="x", rotation=20)
    if not measured:
        axis.text(0.5, 0.55, "not measured", transform=axis.transAxes, ha="center", color=_GRAY, fontsize=14)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _hotspot_chart(analysis: Analysis, path: Path) -> None:
    spots = list(reversed(analysis.hotspots[:8]))
    labels = [item.qualname for item in spots] or ["(none)"]
    values = [item.risk_score for item in spots] or [0]
    colors = []
    for item in spots:
        ratio = item.coverage_ratio
        if ratio is None:
            colors.append(_GRAY)
        elif ratio >= 0.8:
            colors.append(_TEAL)
        elif ratio > 0:
            colors.append(_AMBER)
        else:
            colors.append(_RED)
    if not colors:
        colors = [_GRAY]
    figure, axis = plt.subplots(figsize=(8.2, 4.6))
    axis.barh(labels, values, color=colors)
    axis.set_xlim(0, 1)
    axis.set_xlabel("Heuristic risk score (0–1)")
    axis.set_title("Risk hotspots — color is coverage (red uncovered, amber partial, green covered)")
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _severity_chart(analysis: Analysis, path: Path) -> None:
    order = ["critical", "high", "medium", "low"]
    counts = {name: 0 for name in order}
    for gap in analysis.gaps:
        if gap.severity in counts:
            counts[gap.severity] += 1
    figure, axis = plt.subplots(figsize=(8.2, 4.2))
    axis.bar(order, [counts[name] for name in order], color=[_SEVERITY_COLORS[name] for name in order])
    axis.set_ylabel("Findings")
    axis.set_title("Gap severity")
    for index, name in enumerate(order):
        axis.text(index, counts[name] + 0.05, str(counts[name]), ha="center", va="bottom")
    axis.set_ylim(0, max(counts.values(), default=0) + 1.5)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
