import ast
from pathlib import Path

from recoverage.discover import discover
from recoverage.graph import index_project, louvain, pagerank
from recoverage.mcp_api import handle
from recoverage.models import FunctionSpec, MappedFunction, ProjectProfile
from recoverage.perf import mann_whitney
from recoverage.sbst import search


def test_pagerank_prefers_callees_and_louvain_splits_cliques():
    ranks = pagerank(["hub", "a", "b", "c"], [("a", "hub"), ("b", "hub"), ("c", "hub")])
    assert ranks["hub"] > ranks["a"]
    communities = louvain(
        ["a", "b", "c", "d"],
        [("a", "b"), ("b", "c"), ("c", "a"), ("d", "d")],
    )
    assert communities["a"] == communities["b"] == communities["c"]
    assert communities["d"] != communities["a"]


def test_tree_sitter_byte_ranges_and_mcp(tmp_path: Path):
    fixture = Path(__file__).resolve().parents[1] / "examples" / "fixture"
    graph = index_project(discover(fixture))
    charge = next(entity for entity in graph.entities if entity.symbol == "charge")
    assert charge.start_byte < charge.end_byte
    assert charge.start_line == 6
    listed = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, graph)
    assert listed["result"]["tools"][0]["name"] == "query_context"
    queried = handle(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "query_context", "arguments": {"symbol": "charge"}}},
        graph,
    )
    payload = queried["result"]["content"][0]["text"]
    assert "charge" in payload
    assert "byte_range" in payload


def test_sbst_stall_injects_held_constant(tmp_path: Path):
    (tmp_path / "gate.py").write_text(
        "def allow(token: str) -> str:\n"
        "    if token == 'BEARER_ADMIN_TOKEN':\n"
        "        return 'ok'\n"
        "    return 'no'\n",
        encoding="utf-8",
    )
    profile = ProjectProfile(
        root=str(tmp_path),
        primary_language="python",
        languages=["python"],
        test_runner=None,
        coverage_tool=None,
        test_files=[],
        source_files=["gate.py"],
        entry_points=[],
        packages=[],
        import_root=str(tmp_path),
        src_layout=False,
        flake_markers=[],
    )
    function = MappedFunction(
        spec=FunctionSpec(
            name="allow",
            qualname="allow",
            file="gate.py",
            lineno=1,
            end_lineno=4,
            branch_count=1,
            complexity=2,
            is_public=True,
            risk_score=0.2,
            risk_tags=[],
            parameters=["token"],
        ),
        coverage_ratio=None,
        covered_lines=0,
        executable_lines=3,
        missing_lines=[],
        file_measured=False,
    )
    result = search(profile, [function], client=None, generations=6, population=8, stall_generations=2)
    assert result["stalls"] >= 1
    assert result["cases"]
    blob = str(result)
    assert "BEARER_ADMIN_TOKEN" not in blob
    assert any("<redacted>" in case["args"] or "str" in case["args"] for case in result["cases"])
    assert result["cases"][0]["seed_source"] == "ast-constants"
    ast.parse("pass")


def test_sbst_llm_failure_falls_back_to_ast_constants(tmp_path: Path):
    class Boom:
        name = "boom"

        def complete(self, *, system: str, user: str, timeout: float = 30) -> str:
            raise RuntimeError("down")

    (tmp_path / "gate.py").write_text(
        "def allow(token: str) -> str:\n"
        "    if token == 'BEARER_ADMIN_TOKEN':\n"
        "        return 'ok'\n"
        "    return 'no'\n",
        encoding="utf-8",
    )
    profile = ProjectProfile(
        root=str(tmp_path),
        primary_language="python",
        languages=["python"],
        test_runner=None,
        coverage_tool=None,
        test_files=[],
        source_files=["gate.py"],
        entry_points=[],
        packages=[],
        import_root=str(tmp_path),
        src_layout=False,
        flake_markers=[],
    )
    function = MappedFunction(
        spec=FunctionSpec(
            name="allow",
            qualname="allow",
            file="gate.py",
            lineno=1,
            end_lineno=4,
            branch_count=1,
            complexity=2,
            is_public=True,
            risk_score=0.2,
            risk_tags=[],
            parameters=["token"],
        ),
        coverage_ratio=None,
        covered_lines=0,
        executable_lines=3,
        missing_lines=[],
        file_measured=False,
    )
    result = search(profile, [function], client=Boom(), generations=6, population=8, stall_generations=2)
    assert result["cases"]
    assert result["cases"][0]["seed_source"] == "ast-constants"


def test_search_skips_functions_that_reenter_the_runner(tmp_path: Path):
    (tmp_path / "again.py").write_text(
        "def again(path):\n"
        "    execute_run(path)\n"
        "    return path\n",
        encoding="utf-8",
    )
    profile = ProjectProfile(
        root=str(tmp_path),
        primary_language="python",
        languages=["python"],
        test_runner=None,
        coverage_tool=None,
        test_files=[],
        source_files=["again.py"],
        entry_points=[],
        packages=[],
        import_root=str(tmp_path),
        src_layout=False,
        flake_markers=[],
    )
    function = MappedFunction(
        spec=FunctionSpec(
            name="again",
            qualname="again",
            file="again.py",
            lineno=1,
            end_lineno=3,
            branch_count=0,
            complexity=1,
            is_public=True,
            risk_score=0.0,
            risk_tags=[],
            parameters=["path"],
        ),
        coverage_ratio=None,
        covered_lines=0,
        executable_lines=2,
        missing_lines=[],
        file_measured=False,
    )
    result = search(profile, [function], client=None, generations=2, population=4, stall_generations=2)
    assert result["cases"] == []


def test_search_restores_the_previous_tracer(tmp_path: Path):
    (tmp_path / "gate.py").write_text(
        "def allow(token: str) -> str:\n    return token\n",
        encoding="utf-8",
    )
    seen: list[int] = []

    def sentinel(frame, event, arg):
        if event == "line":
            seen.append(frame.f_lineno)
        return sentinel

    profile = ProjectProfile(
        root=str(tmp_path),
        primary_language="python",
        languages=["python"],
        test_runner=None,
        coverage_tool=None,
        test_files=[],
        source_files=["gate.py"],
        entry_points=[],
        packages=[],
        import_root=str(tmp_path),
        src_layout=False,
        flake_markers=[],
    )
    function = MappedFunction(
        spec=FunctionSpec(
            name="allow",
            qualname="allow",
            file="gate.py",
            lineno=1,
            end_lineno=2,
            branch_count=0,
            complexity=1,
            is_public=True,
            risk_score=0.0,
            risk_tags=[],
            parameters=["token"],
        ),
        coverage_ratio=None,
        covered_lines=0,
        executable_lines=1,
        missing_lines=[],
        file_measured=False,
    )
    import sys

    sys.settrace(sentinel)
    try:
        search(profile, [function], client=None, generations=1, population=2, stall_generations=9)
        assert sys.gettrace() is sentinel
    finally:
        sys.settrace(None)


def test_nested_execute_run_is_refused(tmp_path: Path):
    from recoverage import pipeline

    assert pipeline._LOCK.acquire(blocking=False)
    try:
        try:
            pipeline.execute_run(tmp_path, tmp_path / "out", llm_mode="off")
            raised = False
        except RuntimeError as exc:
            raised = "already running" in str(exc)
        assert raised is True
    finally:
        pipeline._LOCK.release()


def test_mann_whitney_separates_samples():
    _u, same = mann_whitney([1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1])
    _u, different = mann_whitney([1, 1, 1, 1, 1, 1, 1, 1], [9, 9, 9, 9, 9, 9, 9, 9])
    assert same > 0.2
    assert different < 0.05
