import xml.etree.ElementTree as ET

from recoverage.models import ModuleStat
from recoverage.reportview import HotspotRow, ReportView, build_view
from recoverage.svgcharts import coverage_bars, hotspot_bars, score_gauge, severity_bars
from tests.test_reportview import _analysis


def _parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def test_charts_are_well_formed_svg_and_escape_names():
    view = build_view(_analysis(modules=[ModuleStat("<script>", None, 1, 0)]))
    for svg in (score_gauge(view), coverage_bars(view), hotspot_bars(view), severity_bars(view)):
        root = _parse(svg)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
    coverage = coverage_bars(view)
    assert "<script>" not in coverage
    assert "&lt;script&gt;" in coverage
    assert "not measured" in coverage


def test_gauge_prints_the_score_and_hotspot_uses_coverage_color():
    view = build_view(_analysis())
    assert "0.0" in score_gauge(view)
    hostile = ReportView(**{**view.__dict__, "hotspots": (HotspotRow("a<b>", "f.py", 0.4, 0.0, ()),)})
    bars = hotspot_bars(hostile)
    _parse(bars)
    assert "a&lt;b&gt;" in bars
    assert "#9B2335" in bars
