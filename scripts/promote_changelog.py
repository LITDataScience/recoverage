"""Move the Unreleased notes in docs/CHANGELOG.md under the version being tagged.

The Release workflow runs this, commits the result, tags v{version}, and publishes
a GitHub Release. python-publish.yml uploads that tag to PyPI. Do not run it by
hand unless you are about to commit the rewritten changelog.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

_VERSION = re.compile(r'^__version__ = "([^"]+)"\s*$', re.M)
_UNRELEASED = re.compile(r"^## \[Unreleased\]\s*$", re.M)
_RELEASED = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.M)


def read_version(version_py: Path) -> str:
    match = _VERSION.search(version_py.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"no __version__ in {version_py}")
    return match.group(1)


def promote(text: str, version: str, today: str) -> tuple[str, str]:
    """Return (rewritten changelog, release notes). Release notes are the Unreleased body."""
    if _RELEASED.search(text) and version in _RELEASED.findall(text):
        raise SystemExit(f"changelog already has [{version}]")
    found = _UNRELEASED.search(text)
    if found is None:
        raise SystemExit("changelog has no ## [Unreleased] section")
    rest = text[found.end() :]
    nxt = re.search(r"^## \[", rest, re.M)
    body = (rest[: nxt.start()] if nxt else rest).strip()
    if not body:
        raise SystemExit("Unreleased is empty; write the notes before cutting a release")
    heading = f"## [{version}] - {today}"
    rewritten = text[: found.end()].rstrip("\n") + "\n\n" + heading + "\n\n" + body + "\n"
    if nxt:
        rewritten += "\n" + rest[nxt.start() :]
    elif not rewritten.endswith("\n"):
        rewritten += "\n"
    return rewritten, body + "\n"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    version = read_version(root / "src" / "recoverage" / "version.py")
    path = root / "docs" / "CHANGELOG.md"
    rewritten, notes = promote(path.read_text(encoding="utf-8"), version, date.today().isoformat())
    path.write_text(rewritten, encoding="utf-8")
    sys.stdout.write(notes)


if __name__ == "__main__":
    main()
