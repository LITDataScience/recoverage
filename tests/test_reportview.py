from recoverage.models import (
    Analysis,
    CoverageResult,
    FunctionSpec,
    Gap,
    MappedFunction,
    ModuleStat,
    ProjectProfile,
    ScoreFactor,
    ScoreResult,
)
from recoverage.reportview import build_view


def _analysis(**kwargs) -> Analysis:
    coverage = kwargs.pop(
        "coverage",
        CoverageResult(
            tool="static",
            measured=False,
            tool_line_percent=None,
            tool_branch_percent=None,
            line_percent=None,
            branch_percent=None,
            branch_is_tool=False,
            files=[],
            tests_exit_code=None,
            notes=[],
            command=[],
        ),
    )
    project = kwargs.pop(
        "project",
        ProjectProfile(
            root="C:/work/shop",
            primary_language="python",
            languages=["python"],
            test_runner=None,
            coverage_tool=None,
            test_files=[],
            source_files=["cart.py"],
            entry_points=[],
            packages=[],
            import_root=".",
            src_layout=False,
            flake_markers=[],
            notes=["partial"],
        ),
    )
    return Analysis(
        version="0.1.0",
        generated_at="2026-09-25T00:00:00+00:00",
        llm="off",
        project=project,
        coverage=coverage,
        functions=kwargs.get("functions", []),
        modules=kwargs.get("modules", [ModuleStat("shop", None, 10, 0)]),
        hotspots=[],
        gaps=kwargs.get(
            "gaps",
            [Gap("G01", "high", "untested-function", "charge", "why", "pay.py", "charge", "add a test", True)],
        ),
        score=ScoreResult(
            score=0.0,
            gate="blocked",
            factors=[ScoreFactor("structural", "Structural coverage", 0.0, 40, "not measured", False)],
            mutation_testing_ran=False,
            notes=[],
        ),
    )


def test_static_view_says_not_measured_and_names_the_project():
    view = build_view(_analysis())
    assert view.project_name == "shop"
    assert view.measured is False
    assert view.coverage_rows[0].value == "not measured"
    assert view.severity_counts["high"] == 1
    assert view.files[0].path == "pay.py"
    assert view.files[0].worst_gap == "high"
    assert any("no test runner" in view.gate_sentence.lower() or "runner" in view.gate_sentence.lower() for _ in [0])
    assert view.notes == ("partial",)
    assert any("Install coverage" in line for line in view.suggestions)


def test_file_rows_roll_up_functions_and_the_worst_gap():
    spec = FunctionSpec("charge", "charge", "pay.py", 1, 4, 1, 2, True, 0.9, ["payment"], ["amount"])
    function = MappedFunction(spec, 0.5, 2, 4, [3, 4], True)
    view = build_view(_analysis(functions=[function]))
    row = view.files[0]
    assert row.functions == 1
    assert row.statements == 4
    assert row.covered == 2
    assert row.line_percent == 50.0
    assert row.gaps == 1
