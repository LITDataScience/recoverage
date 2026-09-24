import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from recoverage.cli import main
from recoverage.pipeline import execute_generate, execute_report, execute_run
from recoverage.score import RUBRIC_MD

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "fixture"
ROOT = Path(__file__).resolve().parents[1]


def _copy(tmp_path: Path) -> Path:
    project = tmp_path / "shop"
    shutil.copytree(FIXTURE, project)
    (project / "tests" / "do_not_delete.txt").write_text("keep", encoding="utf-8")
    return project


def test_readme_publishes_rubric():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert RUBRIC_MD.strip() in readme
    workflow = (ROOT / "examples" / "ci" / "recoverage.yml").read_text(encoding="utf-8")
    assert "--threshold merge-ready" in workflow


def test_run_fixture_writes_real_report(tmp_path: Path):
    project = _copy(tmp_path)
    original = (project / "tests" / "test_cart.py").read_text(encoding="utf-8")
    output = tmp_path / "out"
    analysis, code = execute_run(project, output, llm_mode="off")
    assert code == 0
    assert analysis.coverage.measured is True
    assert analysis.coverage.tool == "coverage.py"
    assert analysis.coverage.line_percent is not None
    assert analysis.coverage.line_percent < 80
    assert analysis.score.mutation_testing_ran is True
    assert analysis.score.gate == "blocked"
    charge = next(item for item in analysis.functions if item.spec.name == "charge")
    assert charge.coverage_ratio == 0
    assert any(gap.symbol == "charge" and gap.severity == "critical" for gap in analysis.gaps)
    markdown = (output / "report.md").read_text(encoding="utf-8")
    blurb = markdown.split("## Coverage stats", 1)[0]
    assert "no test runner" not in blurb.lower()
    assert "under 20%" in blurb
    assert "under 40" in blurb
    html = (output / "report.html").read_text(encoding="utf-8")
    assert "no test runner" not in html.lower()
    assert "under 20%" in html
    assert "<style>" in html
    assert "data:image/png;base64," in html
    assert "rel=\"stylesheet\"" not in html
    assert f"{analysis.score.score:.1f}" in html
    assert "Findings" in html and "Suggestions" in html
    assert f"{analysis.score.score:.1f}" in markdown
    assert RUBRIC_MD.strip() in markdown
    assert "mutant" in markdown.lower()
    mrs = json.loads((output / "mrs.json").read_text(encoding="utf-8"))
    assert "no test runner" not in mrs["blurb"].lower()
    assert "under 20%" in mrs["blurb"]
    assert (output / "report.typ").is_file()
    assert "Suggestions" in markdown
    assert (output / "charts" / "coverage_by_package.png").read_bytes().startswith(b"\x89PNG")
    assert (output / "charts" / "risk_hotspots.png").read_bytes().startswith(b"\x89PNG")
    assert (output / "charts" / "gap_severity.png").read_bytes().startswith(b"\x89PNG")
    pdf = (output / "report.pdf").read_bytes()
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 4000
    assert (project / "tests" / "test_cart.py").read_text(encoding="utf-8") == original
    assert (project / "tests" / "do_not_delete.txt").read_text(encoding="utf-8") == "keep"
    assert main(["run", str(project), "--output", str(tmp_path / "gated"), "--no-llm", "--threshold", "production-ready"]) == 1
    rerendered, report_code = execute_report(project, output, llm_mode="off")
    assert report_code == 0
    assert rerendered.score.score == analysis.score.score


def test_generate_drafts_are_real_and_safe(tmp_path: Path):
    project = _copy(tmp_path)
    output = tmp_path / "out"
    assert main(["generate", str(project), "--output", str(output), "--no-llm", "--dry-run"]) == 0
    assert list(project.glob("tests/*recoverage*")) == []
    assert (output / "generation-preview.md").is_file()

    first, code = execute_run(project, output, llm_mode="off")
    _, planned = execute_generate(project, output, llm_mode="off", dry_run=False)
    assert len(planned) > 0
    for item in planned:
        path = project / item.path
        assert path.is_file()
        ast.parse(path.read_text(encoding="utf-8"))
    watched = [project / "tests" / "test_cart.py", project / "tests" / "do_not_delete.txt"]
    watched.extend(project.glob("tests/*recoverage*.py"))
    before = {path: path.read_bytes() for path in watched}
    execute_generate(project, output, llm_mode="off", dry_run=False)
    for path, content in before.items():
        assert path.read_bytes() == content
    assert (project / "tests" / "do_not_delete.txt").read_text(encoding="utf-8") == "keep"

    env = os.environ.copy()
    env.pop("RECOVERAGE_LLM_API_KEY", None)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    second, _ = execute_run(project, tmp_path / "out2", llm_mode="off")
    assert second.score.score > first.score.score
    charge = next(item for item in second.functions if item.spec.name == "charge")
    assert charge.coverage_ratio is not None and charge.coverage_ratio > 0


def test_static_fallback_has_no_fake_percent(tmp_path: Path):
    (tmp_path / "lib.go").write_text("package p\nfunc Save(secret string) {}\n", encoding="utf-8")
    output = tmp_path / "out"
    analysis, code = execute_run(tmp_path, output, llm_mode="off")
    assert code == 0
    assert analysis.coverage.measured is False
    assert analysis.coverage.line_percent is None
    assert analysis.score.gate == "blocked"
    text = (output / "report.md").read_text(encoding="utf-8")
    assert "not measured" in text
    cell = text.split("Project statement coverage", 1)[1].split("|", 2)[1]
    assert "not measured" in cell
    assert "0.0%" not in cell
    blurb = text.split("## Coverage stats", 1)[0]
    assert "no test runner" in blurb.lower()
    assert "under 20%" not in blurb.lower()
    html = (output / "report.html").read_text(encoding="utf-8")
    assert "no test runner" in html.lower()
    assert "under 20%" not in html.lower()
