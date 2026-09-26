from recoverage.pipeline import execute_run


def test_project_cov_addopts_do_not_make_pytest_exit_4(tmp_path):
    project = tmp_path / "proj"
    package = project / "src" / "shop"
    tests = project / "tests"
    package.mkdir(parents=True)
    tests.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cart.py").write_text("def add(x):\n    return x\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'addopts = "--cov=shop --cov-fail-under=90"\n'
        'pythonpath = ["src"]\n',
        encoding="utf-8",
    )
    (tests / "test_cart.py").write_text(
        "from shop.cart import add\n\ndef test_add():\n    assert add(1) == 1\n",
        encoding="utf-8",
    )
    analysis, code = execute_run(project, tmp_path / "out", dynamic=True)
    assert analysis.coverage.tests_exit_code == 0
    assert analysis.coverage.measured is True
    assert analysis.coverage.line_percent == 100.0
    assert code == 0


def test_a_conftest_import_error_is_not_reported_as_zero_coverage(tmp_path):
    project = tmp_path / "proj"
    tests = project / "tests"
    tests.mkdir(parents=True)
    (project / "app.py").write_text("def ready():\n    return True\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
    (tests / "conftest.py").write_text("import not_a_real_module_xyz\n", encoding="utf-8")
    (tests / "test_one.py").write_text("def test_one():\n    assert True\n", encoding="utf-8")
    analysis, _code = execute_run(project, tmp_path / "out", dynamic=True)
    assert analysis.coverage.tests_exit_code == 4
    assert analysis.coverage.measured is False
    assert analysis.coverage.line_percent is None
    assert "not_a_real_module_xyz" in analysis.coverage.notes[0]
    assert "traceback" not in analysis.coverage.notes[0].lower()
