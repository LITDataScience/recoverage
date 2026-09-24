from pathlib import Path

from recoverage.discover import discover
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
