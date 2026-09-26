import http.client
from pathlib import Path

from recoverage.cli import main
from recoverage.display import locate_html, serve_html
from recoverage.html_report import build_html
from recoverage.models import (
    Analysis,
    CoverageResult,
    Gap,
    ProjectProfile,
    ScoreFactor,
    ScoreResult,
)


def _analysis() -> Analysis:
    return Analysis(
        version="0.1.0",
        generated_at="2026-09-23T00:00:00+00:00",
        llm="off",
        project=ProjectProfile(
            root=".",
            primary_language="python",
            languages=["python"],
            test_runner="pytest",
            coverage_tool="coverage.py",
            test_files=["tests/test_cart.py"],
            source_files=["src/shop/cart.py"],
            entry_points=[],
            packages=["shop"],
            import_root=".",
            src_layout=True,
            flake_markers=[],
        ),
        coverage=CoverageResult(
            tool="coverage.py",
            measured=True,
            tool_line_percent=14.1,
            tool_branch_percent=10.5,
            line_percent=16.7,
            branch_percent=10.5,
            branch_is_tool=True,
            files=[],
            tests_exit_code=0,
            notes=[],
            command=["pytest"],
        ),
        functions=[],
        modules=[],
        hotspots=[],
        gaps=[Gap("G01", "critical", "untested-function", "charge never ran", "none executed", "payments.py", "charge", "call charge", False)],
        score=ScoreResult(
            score=32.5,
            gate="blocked",
            factors=[ScoreFactor("structural", "Structural coverage", 5.69, 40, "statements 16.7%", False)],
            mutation_testing_ran=True,
            notes=["Not mergeable. Measured statement coverage is 16.7%, under 20%."],
        ),
    )


def test_html_embeds_charts_and_the_real_gate_reasons(tmp_path: Path):
    chart = tmp_path / "coverage_by_package.png"
    chart.write_bytes(b"\x89PNG\r\n\x1a\nrest")
    page = build_html(_analysis(), {"coverage_by_package": chart, "risk_hotspots": tmp_path / "missing.png", "gap_severity": chart})
    assert "<style>" in page
    assert 'rel="stylesheet"' not in page
    assert "<svg" in page
    assert "data:image/png;base64," not in page
    assert "32.5" in page
    assert "blocked" in page
    assert "no test runner" not in page.split("<main>", 1)[0].lower()
    assert "under 20%" in page
    assert "charge never ran" in page
    assert "Suggestions" in page
    assert "<script src=" not in page


def test_show_serves_the_existing_file_and_does_not_rewrite_it(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text("<!DOCTYPE html><p>already written</p>", encoding="utf-8")
    original = html.read_bytes()
    server = serve_html(html, port=0, open_browser=False, background=True)
    try:
        host, port = server.server_address[:2]
        connection = http.client.HTTPConnection(host, port, timeout=2)
        connection.request("GET", "/report.html")
        response = connection.getresponse()
        body = response.read()
        connection.close()
        assert response.status == 200
        assert body == original
        assert html.read_bytes() == original
        assert locate_html(tmp_path) == html.resolve()
    finally:
        server.shutdown()
        server.server_close()


def test_show_refuses_when_no_html_exists(tmp_path: Path):
    assert main(["show", str(tmp_path), "--no-open"]) == 2
    assert not (tmp_path / "report.html").exists()
    assert not (tmp_path / "recoverage-out").exists()
