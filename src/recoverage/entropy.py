"""Prompt-coverage proxy.

Transformer attention heads are not available offline. This is Shannon entropy
over spec tokens versus tokens the tests actually mention. The report says so.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from recoverage.graph import CodeGraph
from recoverage.models import ProjectProfile

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


def prompt_coverage(profile: ProjectProfile, graph: CodeGraph) -> dict:
    specs = []
    for entity in graph.entities:
        if entity.docstring:
            specs.append(entity.docstring)
        if entity.signature:
            specs.append(entity.signature)
    root = Path(profile.root)
    for relative in profile.source_files:
        path = root / relative
        if path.suffix == ".md":
            continue
    readme = root / "README.md"
    if readme.is_file():
        specs.append(readme.read_text(encoding="utf-8", errors="replace"))
    tests = []
    for relative in profile.test_files:
        path = root / relative
        if path.is_file():
            tests.append(path.read_text(encoding="utf-8", errors="replace"))
    spec_tokens = _tokens("\n".join(specs))
    test_tokens = set(_tokens("\n".join(tests)))
    if not spec_tokens:
        return {
            "ran": False,
            "method": "lexical-entropy",
            "h_spec": None,
            "h_residual": None,
            "delta_h": None,
            "coverage": None,
            "note": "No natural-language specification text was found. Prompt coverage was not scored from an LLM.",
        }
    h_spec = _shannon(spec_tokens)
    residual = [token for token in spec_tokens if token not in test_tokens]
    h_residual = _shannon(residual) if residual else 0.0
    delta = max(0.0, h_spec - h_residual)
    coverage = 0.0 if h_spec == 0 else max(0.0, min(100.0, 100.0 * delta / h_spec))
    return {
        "ran": True,
        "method": "lexical-entropy",
        "h_spec": round(h_spec, 4),
        "h_residual": round(h_residual, 4),
        "delta_h": round(delta, 4),
        "coverage": round(coverage, 2),
        "note": (
            "ΔH is the drop in Shannon entropy of specification tokens after removing tokens "
            "named by tests. This is a lexical spotlight, not transformer attention."
        ),
    }


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text)]


def _shannon(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    total = sum(counts.values())
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy
