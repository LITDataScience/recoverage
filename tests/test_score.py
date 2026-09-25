from recoverage.models import CoverageResult, FunctionSpec, Gap, MappedFunction, ProjectProfile, ScoreResult
from recoverage.score import RUBRIC_MD, decide_gate, explain_gate, meets_threshold, score_project


def _profile(**kwargs) -> ProjectProfile:
    base = dict(
        root=".",
        primary_language="python",
        languages=["python"],
        test_runner="pytest",
        coverage_tool="coverage.py",
        test_files=[],
        source_files=[],
        entry_points=[],
        packages=["shop"],
        import_root=".",
        src_layout=False,
        flake_markers=[],
    )
    base.update(kwargs)
    return ProjectProfile(**base)


def _fn(name: str, *, risk: float = 0.0, branches: int = 0, ratio: float | None = 1.0) -> MappedFunction:
    return MappedFunction(
        spec=FunctionSpec(
            name=name,
            qualname=name,
            file=f"{name}.py",
            lineno=1,
            end_lineno=10,
            branch_count=branches,
            complexity=1 + branches,
            is_public=True,
            risk_score=risk,
            risk_tags=["payment"] if risk else [],
            parameters=["amount"],
        ),
        coverage_ratio=ratio,
        covered_lines=10 if ratio else 0,
        executable_lines=10,
        missing_lines=[] if ratio else [2],
        file_measured=ratio is not None,
    )


def _coverage(**kwargs) -> CoverageResult:
    base = dict(
        tool="coverage.py",
        measured=True,
        tool_line_percent=90.0,
        tool_branch_percent=80.0,
        line_percent=90.0,
        branch_percent=80.0,
        branch_is_tool=True,
        files=[],
        tests_exit_code=0,
        notes=[],
        command=["coverage"],
    )
    base.update(kwargs)
    return CoverageResult(**base)


def test_factor_maximums_sum_to_100(tmp_path):
    profile = _profile(root=str(tmp_path))
    result = score_project(profile, _coverage(), [_fn("ok")], [])
    assert sum(factor.maximum for factor in result.factors) == 100
    assert result.mutation_testing_ran is False


def test_unmeasured_cannot_be_merge_ready(tmp_path):
    result = score_project(
        _profile(root=str(tmp_path)),
        _coverage(measured=False, line_percent=None, branch_percent=None, tool_line_percent=None, tool_branch_percent=None, branch_is_tool=False, tests_exit_code=None),
        [_fn("charge", risk=0.9, branches=3, ratio=None)],
        [],
    )
    assert result.gate in {"blocked", "needs-review"}
    assert result.score < 70


def test_gate_table_matches_rubric():
    assert decide_gate(90, runner=False, measured=True, line=90, critical=0, tests_exit_code=0) == "blocked"
    assert decide_gate(30, runner=True, measured=True, line=50, critical=0, tests_exit_code=0) == "blocked"
    assert decide_gate(50, runner=True, measured=True, line=10, critical=0, tests_exit_code=0) == "blocked"
    assert decide_gate(90, runner=True, measured=False, line=None, critical=0) == "needs-review"
    assert decide_gate(75, runner=True, measured=True, line=65, critical=1, tests_exit_code=0) == "needs-review"
    assert decide_gate(75, runner=True, measured=True, line=65, critical=0, tests_exit_code=0) == "merge-ready"
    assert decide_gate(90, runner=True, measured=True, line=88, critical=0, tests_exit_code=0) == "production-ready"
    assert decide_gate(90, runner=True, measured=True, line=50, critical=0, tests_exit_code=0) == "needs-review"


def test_threshold_rank_and_number():
    score = ScoreResult(score=72, gate="merge-ready", factors=[], mutation_testing_ran=False, notes=[])
    assert meets_threshold(score, "needs-review")
    assert meets_threshold(score, "merge-ready")
    assert not meets_threshold(score, "production-ready")
    assert meets_threshold(score, "70")
    assert not meets_threshold(score, "80")
    assert meets_threshold(score, None)


def test_blocked_copy_matches_the_reasons_that_fired(tmp_path):
    low = score_project(
        _profile(root=str(tmp_path), test_runner="pytest"),
        _coverage(line_percent=16.7, branch_percent=10.0, tool_line_percent=14.1, tool_branch_percent=10.0),
        [_fn("charge", risk=0.9, branches=4, ratio=0.0)],
        [],
    )
    assert low.gate == "blocked"
    assert "no test runner" not in low.notes[0].lower()
    assert "under 20%" in low.notes[0]
    assert "under 40" in low.notes[0]
    assert low.notes[0] == explain_gate(
        "blocked",
        score=low.score,
        runner=True,
        measured=True,
        line=16.7,
        critical=0,
        tests_exit_code=0,
    )

    bare = score_project(
        _profile(root=str(tmp_path), test_runner=None),
        _coverage(
            measured=False,
            line_percent=None,
            branch_percent=None,
            tool_line_percent=None,
            tool_branch_percent=None,
            branch_is_tool=False,
            tests_exit_code=None,
        ),
        [],
        [],
    )
    assert bare.gate == "blocked"
    assert "no test runner" in bare.notes[0].lower()
    assert "under 20%" not in bare.notes[0]


def test_rubric_mentions_mutation_honesty():
    assert "If it does not run, the report says it did not run." in RUBRIC_MD
    assert "temp copy" in RUBRIC_MD
    assert "production-ready" in RUBRIC_MD


def test_nonzero_test_exit_blocks_every_named_gate(tmp_path):
    assert decide_gate(90, runner=True, measured=True, line=88, critical=0, tests_exit_code=1) == "blocked"
    text = explain_gate(
        "blocked",
        score=90,
        runner=True,
        measured=True,
        line=88,
        critical=0,
        tests_exit_code=1,
    )
    assert "exited 1" in text
    failed = score_project(
        _profile(root=str(tmp_path)),
        _coverage(line_percent=90.0, branch_percent=90.0, tests_exit_code=1),
        [_fn("ok")],
        [],
        analytics={"pbt": {"ran": True, "trials": 10, "passed": 10}, "timing": {"ran": True, "regression": False}},
    )
    assert failed.gate == "blocked"
    assert "exited 1" in failed.notes[0]
    assert not meets_threshold(failed, "merge-ready")
    assert not meets_threshold(failed, "production-ready")
    assert decide_gate(90, runner=True, measured=True, line=88, critical=0, tests_exit_code=0) == "production-ready"
    assert decide_gate(90, runner=True, measured=True, line=88, critical=0, tests_exit_code=None) == "blocked"
    missing = score_project(
        _profile(root=str(tmp_path)),
        _coverage(line_percent=90.0, branch_percent=90.0, tests_exit_code=None),
        [_fn("ok")],
        [],
    )
    assert missing.tests_failed is True
    assert not meets_threshold(missing, "70")


def test_flake_marker_deducts(tmp_path):
    (tmp_path / "test_flaky.py").write_text("import pytest\n@pytest.mark.flaky\ndef test_a():\n    assert True\n", encoding="utf-8")
    result = score_project(
        _profile(root=str(tmp_path), test_files=["test_flaky.py"], flake_markers=["test_flaky.py: pytest.mark.flaky"]),
        _coverage(),
        [_fn("ok", branches=2)],
        [Gap("G01", "low", "flake-marker", "flaky", "why", "test_flaky.py", None, "fix", True)],
    )
    assert any("flake" in note.lower() for note in result.notes)
    assert result.score <= 100
