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
from recoverage.sources import SourceCache

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


def prompt_coverage(profile: ProjectProfile, graph: CodeGraph, *, cache: SourceCache | None = None) -> dict:
    """Streams tokens into counters. No concatenated corpus string is ever built."""
    root = Path(profile.root)
    cache = cache or SourceCache(root)
    spec_counts: Counter[str] = Counter()
    for entity in graph.entities:
        if entity.docstring:
            spec_counts.update(_tokens(entity.docstring))
        if entity.signature:
            spec_counts.update(_tokens(entity.signature))
    readme = cache.text("README.md")
    if readme:
        spec_counts.update(_tokens(readme))
    test_tokens: set[str] = set()
    for relative in profile.test_files:
        text = cache.text(relative)
        if text:
            test_tokens.update(_tokens(text))
    if not spec_counts:
        return {
            "ran": False,
            "method": "lexical-entropy",
            "h_spec": None,
            "h_residual": None,
            "delta_h": None,
            "coverage": None,
            "note": "No natural-language specification text was found. Prompt coverage was not scored from an LLM.",
        }
    h_spec = _shannon(spec_counts)
    residual = Counter({token: count for token, count in spec_counts.items() if token not in test_tokens})
    h_residual = _shannon(residual)
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


def _shannon(counts: Counter[str] | list[str]) -> float:
    if not isinstance(counts, Counter):
        counts = Counter(counts)
    if not counts:
        return 0.0
    total = sum(counts.values())
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy
