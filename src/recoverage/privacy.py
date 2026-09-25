"""Strip secrets and machine paths before anything is written."""

from __future__ import annotations

import re
from pathlib import Path

_SECRET = re.compile(
    r"("
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|AKIA[0-9A-Z]{16}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|Bearer\s+[A-Za-z0-9._\-]{8,}"
    r"|BEARER_[A-Z0-9_]{6,}"
    r"|eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
    r")",
    re.IGNORECASE,
)
_WIN_ABS = re.compile(r"[A-Za-z]:\\[^\s\"'`<>|*?]+")
# `@/` is a TS path alias, not a filesystem path.
_POSIX_ABS = re.compile(r"(?<![:\w@])/[\w.\-]+(?:/[\w.\-]+)+")


def looks_secret(value: str) -> bool:
    return bool(_SECRET.search(value))


def redact_text(value: str) -> str:
    value = _SECRET.sub("[REDACTED]", value)
    value = _WIN_ABS.sub("<path>", value)
    value = _POSIX_ABS.sub("<path>", value)
    return value


def public_args(args: list) -> list:
    """Type names only. Secret-shaped strings are marked redacted and never copied."""
    out = []
    for value in args:
        if isinstance(value, str) and looks_secret(value):
            out.append("<redacted>")
        elif value is None:
            out.append("none")
        else:
            out.append(type(value).__name__)
    return out


def _scrub_str(value: str, memo: dict[str, str]) -> str:
    cached = memo.get(value)
    if cached is not None:
        return cached
    # Only strings that can start an absolute path pay for a Path() object.
    if value[:1] in ("/", "\\") or value[1:2] == ":":
        path = Path(value)
        if path.is_absolute():
            memo[value] = path.name or "<path>"
            return memo[value]
    cleaned = redact_text(value)
    if len(memo) < 65_536:
        memo[value] = cleaned
    return cleaned


def scrub(value, _memo: dict[str, str] | None = None):
    """Walk a JSON-like tree. Drop docstrings. Redact strings. Basename absolute paths.

    Iterative over lists of scalars, memoised per distinct string, so a report with
    20_000 functions and their statement-line lists does not cost a Python call per int.
    """
    memo = {} if _memo is None else _memo
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if key == "docstring":
                cleaned[key] = ""
            elif isinstance(item, (dict, list)):
                cleaned[key] = scrub(item, memo)
            elif isinstance(item, str):
                cleaned[key] = _scrub_str(item, memo)
            else:
                cleaned[key] = item
        return cleaned
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, (dict, list)):
                out.append(scrub(item, memo))
            elif isinstance(item, str):
                out.append(_scrub_str(item, memo))
            else:
                out.append(item)
        return out
    if isinstance(value, str):
        return _scrub_str(value, memo)
    return value
