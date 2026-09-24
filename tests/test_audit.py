from recoverage.assure import acceptance
from recoverage.audit import audit_project, crap
from recoverage.discover import discover
from recoverage.models import FunctionSpec, MappedFunction


def test_crap_matches_the_uncovered_complexity_table():
    assert crap(15, 0.0) == 240.0
    assert crap(1, 0.0) == 2.0
    assert crap(10, 0.416) <= 30.5


def test_assertion_strength_rejects_tautologies_and_type_checks(tmp_path):
    (tmp_path / "test_weak.py").write_text(
        "def test_tautology():\n"
        "    value = 1\n"
        "    assert value == value\n"
        "    assert True\n"
        "\n"
        "def test_vacuous():\n"
        "    result = {'status': 'captured'}\n"
        "    assert result is not None\n"
        "    assert isinstance(result, dict)\n"
        "\n"
        "def test_substantive():\n"
        "    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    profile = discover(tmp_path)
    report = audit_project(profile, [])
    assertions = report["assertions"]
    assert assertions["total"] == 5
    assert assertions["substantive"] == 1
    assert assertions["asr"] == 20.0
    assert any(item["kind"] == "tautology" for item in assertions["vacuous"])
    assert assertions["magic_numbers"] >= 1


def test_phantom_import_fails_dar_and_time_call_fails_firi(tmp_path):
    (tmp_path / "app.py").write_text("import flask_auth_handler\n", encoding="utf-8")
    (tmp_path / "test_app.py").write_text(
        "import time\n"
        "def test_clock():\n"
        "    assert time.time() > 0\n",
        encoding="utf-8",
    )
    profile = discover(tmp_path)
    report = audit_project(profile, [])
    assert report["authenticity"]["dar"] < 100
    assert report["authenticity"]["phantoms"]
    assert report["flakiness"]["firi"] == 100.0
    assert report["scorecard"][0]["status"] == "FAIL"


def test_package_submodule_import_is_not_unresolved(tmp_path):
    package = tmp_path / "widget"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "pipeline.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "test_widget.py").write_text(
        "from widget import pipeline\n"
        "def test_run():\n"
        "    assert pipeline.run() == 1\n",
        encoding="utf-8",
    )
    report = audit_project(discover(tmp_path), [])
    assert report["authenticity"]["unresolved"] == []
    assert report["authenticity"]["dar"] == 100.0


def test_local_import_is_verified(tmp_path):
    (tmp_path / "shop.py").write_text("def subtotal(prices):\n    return 1\n", encoding="utf-8")
    (tmp_path / "test_shop.py").write_text(
        "from shop import subtotal\n"
        "def test_subtotal_sums_prices():\n"
        "    assert subtotal([1.0]) == 1\n",
        encoding="utf-8",
    )
    profile = discover(tmp_path)
    report = audit_project(profile, [])
    assert report["authenticity"]["dar"] == 100.0
    assert report["authenticity"]["phantoms"] == []


def test_draft_acceptance_is_coverage_or_mutant_kill():
    assert acceptance(True, 0) == "novel-coverage"
    assert acceptance(False, 2) == "mutant-kill"
    assert acceptance(False, 0) is None


def _fn(name: str, complexity: int, ratio: float | None) -> MappedFunction:
    return MappedFunction(
        spec=FunctionSpec(
            name=name,
            qualname=name,
            file=f"{name}.py",
            lineno=1,
            end_lineno=4,
            branch_count=complexity - 1,
            complexity=complexity,
            is_public=True,
            risk_score=0.2,
            risk_tags=[],
            parameters=[],
        ),
        coverage_ratio=ratio,
        covered_lines=0,
        executable_lines=3,
        missing_lines=[],
        file_measured=ratio is not None,
    )


def test_crap_hotspot_threshold():
    report = audit_project(
        discover_profile_placeholder(),
        [_fn("charge", 6, 0.0), _fn("ok", 2, 1.0)],
    )
    assert report["crap"]["count_over_30"] == 1
    assert report["crap"]["hotspots"][0]["symbol"] == "charge"


def discover_profile_placeholder():
    from pathlib import Path
    import tempfile

    root = Path(tempfile.mkdtemp())
    (root / "charge.py").write_text("def charge():\n    return 1\n", encoding="utf-8")
    return discover(root)
