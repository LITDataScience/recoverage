from pathlib import Path

from recoverage.discover import discover
from recoverage.gaps import find_gaps
from recoverage.models import FunctionSpec, MappedFunction
from recoverage.privacy import redact_text
from recoverage.structure import analyze_project, attach_sources

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "fixture"


def test_fixture_discovery():
    profile = discover(FIXTURE)
    assert profile.primary_language == "python"
    assert profile.test_runner == "pytest"
    assert profile.coverage_tool == "coverage.py"
    assert profile.src_layout is True
    assert "shop" in profile.packages
    assert any(path.endswith("test_cart.py") for path in profile.test_files)
    assert any(path.endswith("payments.py") for path in profile.source_files)
    assert not any(path.endswith("test_cart.py") for path in profile.source_files)


def test_nested_manifest_is_not_the_parent_project():
    root = Path(__file__).resolve().parents[1]
    profile = discover(root)
    assert not any("examples/fixture" in path for path in profile.source_files)
    assert not any(path.endswith("test_cart.py") for path in profile.test_files)
    assert any(path.endswith("score.py") for path in profile.source_files)
    assert not any("test_score.py" in item for item in profile.flake_markers)
    assert "examples/fixture" in profile.skipped_projects


def test_python_risk_and_branches():
    profile = discover(FIXTURE)
    structures = analyze_project(profile)
    attach_sources(structures, Path(profile.root))
    by_name = {fn.qualname: fn for structure in structures for fn in structure.functions}
    assert by_name["charge"].risk_score >= 0.7
    assert "payment" in by_name["charge"].risk_tags
    assert by_name["charge"].branch_count >= 3
    assert by_name["subtotal"].branch_count >= 2
    assert by_name["subtotal"].parameters == ["prices"]


def test_javascript_and_generic(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pay.js").write_text(
        "function charge(amount, method) {\n  if (amount <= 0) { throw new Error('amount'); }\n  return {status: 'ok'};\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "refund.js").write_text(
        "function refund(amount) {\n  if (amount <= 0) { throw new Error('amount'); }\n  return amount;\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "main.go").write_text("package main\nfunc Charge(amount int) int {\n  return amount\n}\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name":"demo","devDependencies":{}}\n', encoding="utf-8")
    profile = discover(tmp_path)
    assert profile.primary_language == "javascript"
    assert profile.coverage_tool is None
    structures = analyze_project(profile)
    js = next(item for item in structures if item.path.endswith("pay.js"))
    assert any(fn.name == "charge" for fn in js.functions)
    go = next(item for item in structures if item.path.endswith("main.go"))
    assert any(fn.name == "Charge" for fn in go.functions)
    assert go.language == "go"


def test_walk_prunes_node_modules_and_records_workspaces(tmp_path: Path):
    (tmp_path / "app.ts").write_text("export function ping() { return 1 }\n", encoding="utf-8")
    nested = tmp_path / "node_modules" / "left-pad"
    nested.mkdir(parents=True)
    (nested / "index.js").write_text("module.exports = 1\n", encoding="utf-8")
    web = tmp_path / "apps" / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text('{"name":"web"}\n', encoding="utf-8")
    (web / "page.tsx").write_text("export function Page() { return null }\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name":"root"}\n', encoding="utf-8")
    profile = discover(tmp_path)
    assert profile.source_files == ["app.ts"]
    assert profile.skipped_projects == ["apps/web"]
    assert any("apps/web" in note for note in profile.notes)
    from dataclasses import replace

    from recoverage.host import HostBudget

    capped = discover(tmp_path, replace(HostBudget.baseline(), walk_files=1))
    assert any("partial" in note for note in capped.notes)


def test_package_json_does_not_override_a_larger_python_tree(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"root"}\n', encoding="utf-8")
    (tmp_path / "bootstrap.js").write_text("function boot() { return 1 }\n", encoding="utf-8")
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text("def run():\n    return 1\n", encoding="utf-8")
    assert discover(tmp_path).primary_language == "python"


def test_manifest_wins_primary_language_over_a_larger_file_count(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("def charge(amount):\n    return amount\n", encoding="utf-8")
    for index in range(4):
        (tmp_path / f"extra{index}.js").write_text("function extra() { return 1 }\n", encoding="utf-8")
    profile = discover(tmp_path)
    assert profile.primary_language == "python"


def test_coverage_match_requires_a_unique_path_boundary():
    from recoverage.mapcov import match_coverage
    from recoverage.models import FileCoverage

    def row(path: str) -> FileCoverage:
        return FileCoverage(path, 0, 0, 0, 0, 0, 0, [], [])

    files = {
        "a/pay.py": row("a/pay.py"),
        "b/pay.py": row("b/pay.py"),
    }
    assert match_coverage("pay.py", files) is None
    assert match_coverage("a/pay.py", files).path == "a/pay.py"
    assert match_coverage("pkg/a/pay.py", {"a/pay.py": row("a/pay.py")}).path == "a/pay.py"


def test_package_json_test_script_is_the_command(tmp_path: Path):
    from recoverage.adapters.javascript_cov import _test_command

    (tmp_path / "package.json").write_text(
        '{"scripts":{"test":"vitest run --reporter=dot"}}\n',
        encoding="utf-8",
    )
    profile = discover(tmp_path)
    assert _test_command(profile) == ["npx", "--no-install", "vitest", "run", "--reporter=dot"]


def test_analysis_json_rejects_the_wrong_version_and_a_huge_file(tmp_path: Path, monkeypatch):
    from recoverage.models import load_analysis

    path = tmp_path / "analysis.json"
    path.write_text('{"version":"9.9.9"}', encoding="utf-8")
    try:
        load_analysis(path)
    except ValueError as exc:
        assert "version" in str(exc)
    else:
        raise AssertionError("wrong version was accepted")
    monkeypatch.setattr("recoverage.models.MAX_ANALYSIS_BYTES", 8)
    path.write_text('{"version":"0.1.0"}', encoding="utf-8")
    try:
        load_analysis(path)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("oversized analysis was accepted")


def test_gap_markdown_cannot_become_an_image():
    from recoverage.report import _md

    escaped = _md("see ![x](https://evil.example/a.png)")
    assert "![" not in escaped
    assert "https://evil.example" in escaped


def test_timing_does_not_import_the_project_here(tmp_path: Path):
    import sys

    from recoverage.models import ProjectProfile
    from recoverage.perf import time_functions

    (tmp_path / "shop.py").write_text("def charge(amount):\n    return amount\n", encoding="utf-8")
    profile = ProjectProfile(
        root=str(tmp_path),
        primary_language="python",
        languages=["python"],
        test_runner="pytest",
        coverage_tool="coverage.py",
        test_files=[],
        source_files=["shop.py"],
        entry_points=[],
        packages=[],
        import_root=str(tmp_path),
        src_layout=False,
        flake_markers=[],
    )
    before = list(sys.path)
    result = time_functions(profile, [_fn("charge")], repeats=3)
    assert sys.path == before
    assert "shop" not in sys.modules
    assert result["ran"] is True


def test_a_longer_list_raises_the_timing_allowance():
    from recoverage.perf import _work_ratio

    function = _fn("subtotal")
    function.spec.parameters = ["prices"]
    ratio = _work_ratio(function)
    assert ratio == 200 / 3
    assert 14 < 8 * ratio


def test_alias_import_is_not_redacted_as_a_path():
    text = 'import { Button } from "@/components/ui/button"'
    assert redact_text(text) == text
    assert redact_text("loaded /usr/local/lib/demo") == "loaded <path>"


def test_missing_runner_suggestion_is_grammatical():
    profile = _profile(test_runner=None)
    gaps = find_gaps(profile, [_fn("startPayment")])
    gap = next(item for item in gaps if item.kind == "unmeasured-function")
    assert "a the " not in gap.suggestion
    assert "a test that calls startPayment" in gap.suggestion
    named = find_gaps(_profile(test_runner="pytest"), [_fn("charge")])
    named_gap = next(item for item in named if item.kind == "unmeasured-function")
    assert "a pytest test that calls charge" in named_gap.suggestion


def test_source_cache_reads_once_and_evicts_by_bytes(tmp_path: Path, monkeypatch):
    from recoverage.sources import SourceCache

    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("y = 2\n", encoding="utf-8")
    cache = SourceCache(tmp_path, budget=8)
    reads = []
    original = Path.read_text

    def counting(self, *args, **kwargs):
        reads.append(self.name)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting)
    assert cache.text("a.py") == "x = 1\n"
    assert cache.text("a.py") == "x = 1\n"
    assert reads == ["a.py"]
    assert cache.tree("a.py") is not None
    assert cache.tree("a.py") is cache.tree("a.py")
    cache.text("b.py")  # 12 bytes > budget of 8: a.py is evicted, b.py stays
    assert "a.py" not in cache._text
    assert cache.text("missing.py") is None
    assert cache.tree("missing.py") is None


def test_coverage_index_matches_exact_then_unique_basename():
    from recoverage.mapcov import CoverageIndex
    from recoverage.models import FileCoverage

    def cov(path):
        return FileCoverage(
            path=path,
            covered_lines=0,
            num_statements=0,
            percent_covered=0.0,
            covered_branches=0,
            num_branches=0,
            percent_covered_branches=None,
            executed_lines=[1, 2],
            missing_lines=[3],
        )

    index = CoverageIndex([cov("src/shop/cart.py"), cov("src/other/cart.py"), cov("src/shop/pay.py")])
    assert index.match("src/shop/pay.py").path == "src/shop/pay.py"
    assert index.match("shop/pay.py").path == "src/shop/pay.py"
    assert index.match("cart.py") is None  # two candidates, ambiguous
    assert index.match("other/cart.py").path == "src/other/cart.py"
    assert index.match("nothing.py") is None
    executed, missing = index.lines(index.match("src/shop/pay.py"))
    assert executed == frozenset({1, 2}) and missing == frozenset({3})
    assert index.lines(index.match("src/shop/pay.py")) is index.lines(index.match("src/shop/pay.py"))


def test_body_metrics_match_the_recursive_definition():
    import ast

    from recoverage.structure import _body_metrics, iter_statements

    source = (
        "def outer(a, b):\n"
        "    if a and b or not a:\n"
        "        pass\n"
        "    for i in range(3):\n"
        "        x = [j for j in range(i) if j if j > 1]\n"
        "    def inner():\n"
        "        if a:\n"
        "            return 1\n"
        "    try:\n"
        "        y = a if b else 0\n"
        "    except ValueError:\n"
        "        pass\n"
        "    return inner()\n"
    )
    tree = ast.parse(source)
    outer = tree.body[0]
    decisions, lines = _body_metrics(outer)
    # if(1) + BoolOp or(1) + BoolOp and(1) + for(1) + comprehension ifs(2) + IfExp(1) + ExceptHandler(1); inner is its own scope
    assert decisions == 8
    # 11 is the `except` handler, which is not an ast.stmt, same as the recursive version.
    assert lines == [1, 2, 3, 4, 5, 9, 10, 12, 13]
    statements = [type(node).__name__ for node in iter_statements(tree)]
    assert statements.count("FunctionDef") == 2
    assert "Return" in statements and "Pass" in statements


def test_scrub_is_memoised_and_leaves_ints_alone():
    from recoverage.privacy import scrub

    payload = {
        "docstring": "secret words",
        "functions": [{"file": "C:\\work\\shop\\pay.py", "statement_lines": [1, 2, 3], "note": "token ghp_" + "a" * 24}] * 3,
        "root": "/home/me/project",
    }
    cleaned = scrub(payload)
    assert cleaned["docstring"] == ""
    # POSIX-absolute on POSIX becomes the basename; on Windows Path() does not call it absolute and the regex takes over.
    assert cleaned["root"] in ("project", "<path>")
    # Basename when Path treats it as absolute (Windows). The regex replaces the whole
    # string on POSIX, where C:\... is not an absolute path. Either result leaks nothing.
    assert cleaned["functions"][0]["file"] in {"pay.py", "<path>"}
    assert cleaned["functions"][0]["statement_lines"] == [1, 2, 3]
    assert "[REDACTED]" in cleaned["functions"][2]["note"]


def test_temp_copy_keeps_links_as_links_and_skips_dependency_dirs(tmp_path: Path):
    import os
    import shutil

    from recoverage.proc import temp_copy

    root = tmp_path / "proj"
    (root / "node_modules" / "left-pad").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "pkg").mkdir()
    (root / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("do not copy me\n", encoding="utf-8")
    link = root / "pkg" / "link.txt"
    try:
        os.symlink(outside, link)
        linked = True
    except (OSError, NotImplementedError):
        linked = False
    parent, copied = temp_copy(root, prefix="recoverage-test-")
    try:
        assert (copied / "pkg" / "a.py").is_file()
        assert not (copied / "node_modules").exists()
        assert not (copied / ".git").exists()
        if linked:
            assert (copied / "pkg" / "link.txt").is_symlink()
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def test_blast_radius_is_empty_without_a_diff_and_sized_with_one():
    from recoverage.blast import blast_radius
    from recoverage.graph import CodeGraph, Entity
    from recoverage.models import CoverageResult

    def entity(name):
        return Entity(symbol=name, qualname=name, file="shop.py", kind="function", start_line=1, end_line=2, start_byte=0, end_byte=1, signature=name, docstring="", calls=[], imports=[])

    graph = CodeGraph(
        entities=[entity("a"), entity("b"), entity("c")],
        edges=[("a", "b", "call"), ("b", "c", "call")],
        pagerank={"a": 0.3, "b": 0.3, "c": 0.3},
        communities={"a": 0, "b": 0, "c": 0},
        tree_sitter=True,
    )
    coverage = CoverageResult(
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
    )
    whole = blast_radius(graph, [], coverage, None)
    assert whole["diff"] is False and whole["radius"] == [] and whole["radius_size"] == 3
    diff = blast_radius(graph, [], coverage, ["a"])
    assert diff["diff"] is True and diff["radius"] == ["a", "b", "c"] and diff["radius_size"] == 3
    context = graph.query_context("b", limit=5)
    assert context["found"] is True
    assert {item["symbol"] for item in context["dependencies"]} == {"a", "c"}


def _profile(**kwargs):
    from recoverage.models import ProjectProfile

    base = dict(
        root=".",
        primary_language="typescript",
        languages=["typescript"],
        test_runner=None,
        coverage_tool=None,
        test_files=[],
        source_files=["app.ts"],
        entry_points=[],
        packages=[],
        import_root=".",
        src_layout=False,
        flake_markers=[],
    )
    base.update(kwargs)
    return ProjectProfile(**base)


def _fn(name: str) -> MappedFunction:
    return MappedFunction(
        spec=FunctionSpec(
            name=name,
            qualname=name,
            file="shop.py",
            lineno=1,
            end_lineno=4,
            branch_count=3,
            complexity=4,
            is_public=True,
            risk_score=0.8,
            risk_tags=["payment"],
            parameters=["amount"],
        ),
        coverage_ratio=None,
        covered_lines=0,
        executable_lines=0,
        missing_lines=[],
        file_measured=False,
    )
