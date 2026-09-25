from scripts.promote_changelog import promote, read_version


def test_promote_moves_unreleased_under_the_version(tmp_path):
    version_py = tmp_path / "version.py"
    version_py.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    text = "# Changelog\n\n## [Unreleased]\n\n- first\n- second\n"
    rewritten, notes = promote(text, read_version(version_py), "2026-09-25")
    assert notes == "- first\n- second\n"
    assert "## [Unreleased]\n\n## [0.1.0] - 2026-09-25\n\n- first\n- second\n" in rewritten


def test_promote_keeps_older_releases_and_rejects_a_repeat():
    text = "# Changelog\n\n## [Unreleased]\n\n- next\n\n## [0.1.0] - 2026-01-01\n\n- old\n"
    rewritten, notes = promote(text, "0.2.0", "2026-09-25")
    assert notes.startswith("- next")
    assert rewritten.index("[0.2.0]") < rewritten.index("[0.1.0]")
    assert "- old" in rewritten
    try:
        promote(rewritten, "0.2.0", "2026-09-25")
    except SystemExit as exc:
        assert "already" in str(exc)
    else:
        raise AssertionError("repeated version was accepted")


def test_promote_rejects_an_empty_unreleased():
    try:
        promote("# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n- old\n", "0.2.0", "2026-09-25")
    except SystemExit as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("empty Unreleased was accepted")
