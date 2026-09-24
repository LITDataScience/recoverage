"""Blast radius on the call graph and union coverage inside that radius."""

from __future__ import annotations

from recoverage.graph import CodeGraph
from recoverage.models import CoverageResult, MappedFunction


def blast_radius(
    graph: CodeGraph,
    functions: list[MappedFunction],
    coverage: CoverageResult,
    changed: list[str] | None = None,
) -> dict:
    symbols = [entity.qualname for entity in graph.entities]
    seeds = list(changed or [])
    diff = bool(seeds)
    if not seeds:
        seeds = symbols
    radius = _walk(graph, seeds)
    if not radius:
        radius = set(seeds)
    in_radius = [item for item in functions if item.spec.qualname in radius or item.spec.name in radius]
    executable = sum(item.executable_lines for item in in_radius)
    covered = sum(item.covered_lines for item in in_radius)
    if executable:
        union = round(100.0 * covered / executable, 2)
    elif coverage.line_percent is not None and not diff:
        union = coverage.line_percent
    else:
        union = None
    note = (
        "No diff was supplied. The radius is the whole indexed graph, so union coverage "
        "collapses to coverage of those functions."
        if not diff
        else "Union coverage is statement coverage of functions reachable from the changed symbols."
    )
    return {
        "diff": diff,
        "radius": sorted(radius),
        "union_coverage": union,
        "functions": len(in_radius),
        "note": note,
    }


def _walk(graph: CodeGraph, seeds: list[str]) -> set[str]:
    known = {entity.qualname for entity in graph.entities}
    start = set()
    for seed in seeds:
        if seed in known:
            start.add(seed)
        else:
            start.update(item for item in known if item.endswith("." + seed) or item == seed)
    if not start:
        return set()
    incoming: dict[str, set[str]] = {name: set() for name in known}
    outgoing: dict[str, set[str]] = {name: set() for name in known}
    for src, dst, _kind in graph.edges:
        outgoing.setdefault(src, set()).add(dst)
        incoming.setdefault(dst, set()).add(src)
    seen = set(start)
    frontier = list(start)
    depth = 0
    while frontier and depth < 2:
        nxt = []
        for node in frontier:
            for other in outgoing.get(node, ()) | incoming.get(node, ()):
                if other not in seen:
                    seen.add(other)
                    nxt.append(other)
        frontier = nxt
        depth += 1
    return seen
