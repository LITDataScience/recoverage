"""Read each project file once per run.

Structure, risk, audit, gaps, entropy, PBT, and SBST all read the same files.
Without a cache that is five to seven passes over the tree. This is one, bounded
by bytes so a large tree cannot pin the whole checkout in memory.
"""

from __future__ import annotations

import ast
from collections import OrderedDict
from pathlib import Path

MAX_CACHE_BYTES = 64_000_000


class SourceCache:
    """LRU by bytes. Text is decoded once; parsed Python ASTs are kept alongside."""

    def __init__(self, root: Path, *, budget: int = MAX_CACHE_BYTES):
        self.root = Path(root)
        self.budget = budget
        self._text: OrderedDict[str, str] = OrderedDict()
        self._tree: dict[str, ast.AST | None] = {}
        self._bytes = 0

    def text(self, relative: str) -> str | None:
        cached = self._text.get(relative)
        if cached is not None:
            self._text.move_to_end(relative)
            return cached
        path = self.root / relative
        try:
            value = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        self._text[relative] = value
        self._bytes += len(value)
        while self._bytes > self.budget and len(self._text) > 1:
            evicted, old = self._text.popitem(last=False)
            self._bytes -= len(old)
            self._tree.pop(evicted, None)
        return value

    def tree(self, relative: str) -> ast.AST | None:
        """Parsed module, or None when the file is missing or does not parse."""
        if relative in self._tree:
            return self._tree[relative]
        text = self.text(relative)
        if text is None:
            self._tree[relative] = None
            return None
        try:
            parsed = ast.parse(text)
        except (SyntaxError, ValueError):
            parsed = None
        self._tree[relative] = parsed
        return parsed

    def clear(self) -> None:
        self._text.clear()
        self._tree.clear()
        self._bytes = 0
