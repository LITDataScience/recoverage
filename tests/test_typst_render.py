from pathlib import Path

from recoverage.typst_render import _find_typst


def test_typst_is_found_in_the_winget_links_directory(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("recoverage.typst_render.shutil.which", lambda _name: None)
    monkeypatch.setattr("recoverage.typst_render.Path.home", lambda: tmp_path / "home")
    link = tmp_path / "Microsoft" / "WinGet" / "Links" / "typst.exe"
    link.parent.mkdir(parents=True)
    link.write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert _find_typst() == str(link)
