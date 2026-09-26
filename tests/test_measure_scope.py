from recoverage.mapcov import map_coverage, module_stats
from recoverage.models import (
    CoverageResult,
    FileCoverage,
    FileStructure,
    FunctionSpec,
    MappedFunction,
    ProjectProfile,
)
from recoverage.pbt import _targets, run_properties


def _spec(name: str, file: str) -> FunctionSpec:
    return FunctionSpec(
        name=name,
        qualname=name,
        file=file,
        lineno=1,
        end_lineno=2,
        branch_count=1,
        complexity=1,
        is_public=True,
        risk_score=0.1,
        risk_tags=[],
        parameters=["n"],
    )


def _coverage() -> CoverageResult:
    return CoverageResult(
        tool="coverage.py",
        measured=True,
        tool_line_percent=100.0,
        tool_branch_percent=100.0,
        line_percent=100.0,
        branch_percent=100.0,
        branch_is_tool=True,
        files=[
            FileCoverage(
                path="shop.py",
                covered_lines=1,
                num_statements=1,
                percent_covered=100.0,
                covered_branches=0,
                num_branches=0,
                percent_covered_branches=None,
                executed_lines=[1],
                missing_lines=[],
            )
        ],
        tests_exit_code=0,
        notes=[],
        command=["pytest"],
    )


def test_javascript_is_not_zero_when_only_python_was_measured():
    structures = [
        FileStructure("shop.py", "python", "shop", "shop", 2, 1, [_spec("add", "shop.py")]),
        FileStructure("web/app.js", "javascript", "web", "web.app", 10, 4, [_spec("start", "web/app.js")]),
    ]
    mapped = map_coverage(structures, _coverage())
    js = next(item for item in mapped if item.spec.file.endswith(".js"))
    assert js.coverage_ratio is None
    assert js.file_measured is False
    stats = module_stats(structures, _coverage())
    web = next(item for item in stats if item.name == "web.app")
    assert web.line_percent is None


def test_property_targets_prefer_the_covered_package(tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "wrap.py").write_text("def wrap(n):\n    return n\n", encoding="utf-8")
    (tmp_path / "sanjeevani.py").write_text("def parse(n):\n    return n\n", encoding="utf-8")
    functions = [
        MappedFunction(_spec("wrap", "legacy/wrap.py"), 0.0, 0, 1, [1], False),
        MappedFunction(_spec("parse", "sanjeevani.py"), 1.0, 1, 1, [], True),
    ]
    profile = ProjectProfile(
        root=str(tmp_path),
        primary_language="python",
        languages=["python"],
        test_runner="pytest",
        coverage_tool="coverage.py",
        test_files=[],
        source_files=["legacy/wrap.py", "sanjeevani.py"],
        entry_points=[],
        packages=["sanjeevani"],
        import_root=str(tmp_path),
        src_layout=False,
        flake_markers=[],
    )
    chosen = _targets(profile, functions, limit=1)
    assert [item.spec.name for item in chosen] == ["parse"]


def test_a_function_that_always_raises_is_left_out_of_the_property_score(tmp_path):
    (tmp_path / "good.py").write_text("def add(n):\n    return 1\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def boom(n):\n    raise RuntimeError('no')\n", encoding="utf-8")
    profile = ProjectProfile(
        root=str(tmp_path),
        primary_language="python",
        languages=["python"],
        test_runner="pytest",
        coverage_tool="coverage.py",
        test_files=[],
        source_files=["good.py", "bad.py"],
        entry_points=[],
        packages=[],
        import_root=str(tmp_path),
        src_layout=False,
        flake_markers=[],
    )
    functions = [
        MappedFunction(_spec("boom", "bad.py"), None, 0, 1, [], False),
        MappedFunction(_spec("add", "good.py"), None, 0, 1, [], False),
    ]
    result = run_properties(profile, functions, trials=4)
    assert result["failed"] == 0
    assert result["passed"] > 0
    assert "left out of the score" in result["note"]
    boom = next(row for row in result["properties"] if row["symbol"] == "boom")
    assert boom["trials"] == 0
