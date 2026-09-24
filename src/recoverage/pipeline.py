"""Discover, measure, score, and write reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from recoverage.version import __version__
from recoverage.adapters import collect_coverage
from recoverage.audit import attach_measurements, audit_project
from recoverage.assure import assure_and_write
from recoverage.blast import blast_radius
from recoverage.charts import write_charts
from recoverage.discover import discover
from recoverage.drafts import render_drafts
from recoverage.entropy import prompt_coverage
from recoverage.gaps import find_gaps, parse_error_gaps
from recoverage.generate import PlannedTest
from recoverage.graph import index_project
from recoverage.llm import client_from_env, enrich_gaps
from recoverage.mapcov import hotspots, map_coverage, module_stats
from recoverage.models import Analysis, analysis_from_dict, analysis_to_dict
from recoverage.mutate import run_mutants
from recoverage.pbt import run_properties
from recoverage.perf import time_functions
from recoverage.report import write_reports
from recoverage.sbst import search
from recoverage.score import meets_threshold, score_project
from recoverage.structure import analyze_project, attach_sources


def run_analysis(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "auto",
    client=None,
) -> Analysis:
    profile = discover(path)
    structures = analyze_project(profile)
    attach_sources(structures, Path(profile.root))
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage = collect_coverage(profile, structures, output_dir)
    functions = map_coverage(structures, coverage)
    modules = module_stats(structures, coverage)
    spots = hotspots(functions)
    extra = parse_error_gaps(
        [(item.path, item.parse_error) for item in structures if item.parse_error]
    )
    gaps = find_gaps(profile, functions, extra)
    llm_client = client if client is not None else client_from_env(mode=llm_mode)
    gaps, llm_name = enrich_gaps(gaps, llm_client)
    if llm_mode == "off":
        llm_name = "off"
    graph = index_project(profile)
    pbt = run_properties(profile, functions)
    mutation = run_mutants(profile, functions)
    prompt = prompt_coverage(profile, graph)
    blast = blast_radius(graph, functions, coverage)
    timing = time_functions(profile, functions)
    sbst = search(profile, functions, client=llm_client)
    audit = attach_measurements(
        audit_project(profile, functions),
        line_percent=coverage.line_percent,
        branch_percent=coverage.branch_percent,
        measured=coverage.measured,
        mutation=mutation,
    )
    analytics = _analytics(graph, pbt, mutation, prompt, blast, timing, sbst, audit)
    score = score_project(profile, coverage, functions, gaps, analytics)
    analysis = Analysis(
        version=__version__,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        llm=llm_name,
        project=profile,
        coverage=coverage,
        functions=functions,
        modules=modules,
        hotspots=spots,
        gaps=gaps,
        score=score,
        analytics=analytics,
    )
    _write_analysis(output_dir, analysis)
    return analysis


def write_analysis_reports(analysis: Analysis, output_dir: Path) -> tuple[Path, Path, Path]:
    charts = write_charts(analysis, output_dir)
    return write_reports(analysis, output_dir, charts)


_DEPTH = 0


def _enter():
    global _DEPTH
    if _DEPTH:
        raise RuntimeError("recoverage is already running in this process")
    _DEPTH += 1


def _leave() -> None:
    global _DEPTH
    _DEPTH -= 1


def execute_run(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "auto",
    threshold: str | None = None,
    client=None,
) -> tuple[Analysis, int]:
    _enter()
    try:
        analysis = run_analysis(path, output_dir, llm_mode=llm_mode, client=client)
        write_analysis_reports(analysis, output_dir)
        ok = meets_threshold(analysis.score, threshold)
        return analysis, 0 if ok else 1
    finally:
        _leave()


def execute_report(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "auto",
    threshold: str | None = None,
    analysis_path: Path | None = None,
) -> tuple[Analysis, int]:
    _enter()
    try:
        return _execute_report(path, output_dir, llm_mode=llm_mode, threshold=threshold, analysis_path=analysis_path)
    finally:
        _leave()


def _execute_report(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "auto",
    threshold: str | None = None,
    analysis_path: Path | None = None,
) -> tuple[Analysis, int]:
    source = analysis_path or (output_dir / "analysis.json")
    if source.is_file():
        analysis = analysis_from_dict(json.loads(source.read_text(encoding="utf-8")))
    else:
        analysis = run_analysis(path, output_dir, llm_mode=llm_mode)
    write_analysis_reports(analysis, output_dir)
    return analysis, 0 if meets_threshold(analysis.score, threshold) else 1


def execute_generate(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "auto",
    dry_run: bool = False,
    client=None,
) -> tuple[Analysis, list[PlannedTest]]:
    analysis_path = output_dir / "analysis.json"
    if analysis_path.is_file():
        analysis = analysis_from_dict(json.loads(analysis_path.read_text(encoding="utf-8")))
    else:
        analysis = run_analysis(path, output_dir, llm_mode=llm_mode, client=client)
    drafted = render_drafts(analysis)
    applied, trace = assure_and_write(analysis, drafted, dry_run=dry_run)
    analysis.analytics.setdefault("agents", []).extend(trace)
    output_dir.mkdir(parents=True, exist_ok=True)
    preview = output_dir / "generation-preview.md"
    manifest = {
        "dry_run": dry_run,
        "files": [{"path": item.path, "action": item.action} for item in applied],
    }
    (output_dir / "generation-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    parts = ["# Recoverage generation preview", ""]
    if not applied:
        parts.append("No test drafts survived. Either nothing was safe to draft, or the sandbox filters rejected the files.")
    for item in applied:
        parts.append(f"## {item.action}: `{item.path}`")
        parts.append("")
        parts.append("```")
        parts.append(item.content.rstrip())
        parts.append("```")
        parts.append("")
    preview.write_text("\n".join(parts), encoding="utf-8")
    return analysis, applied


def _analytics(graph, pbt, mutation, prompt, blast, timing, sbst, audit) -> dict:
    ranked = sorted(graph.pagerank.items(), key=lambda item: -item[1])
    return {
        "graph": {
            "tree_sitter": graph.tree_sitter,
            "entities": [
                {
                    "symbol": entity.qualname,
                    "file": entity.file,
                    "start_line": entity.start_line,
                    "end_line": entity.end_line,
                    "start_byte": entity.start_byte,
                    "end_byte": entity.end_byte,
                    "signature": entity.signature,
                    "docstring": entity.docstring,
                }
                for entity in graph.entities
            ],
            "pagerank": [
                {
                    "symbol": symbol,
                    "pagerank": score,
                    "community": graph.communities.get(symbol),
                }
                for symbol, score in ranked
            ],
            "communities": [
                {"id": community, "symbols": [symbol for symbol, cid in graph.communities.items() if cid == community]}
                for community in sorted(set(graph.communities.values()))
            ],
            "edges": [{"src": src, "dst": dst, "kind": kind} for src, dst, kind in graph.edges],
        },
        "pbt": pbt,
        "mutation": mutation,
        "prompt": prompt,
        "blast": blast,
        "timing": timing,
        "audit": audit,
        "sbst": {"cases": sbst.get("cases", []), "stalls": sbst.get("stalls", 0), "llm": sbst.get("llm", False)},
        "agents": list(sbst.get("agents") or []),
    }


def _write_analysis(output_dir: Path, analysis: Analysis) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(
        json.dumps(analysis_to_dict(analysis), indent=2),
        encoding="utf-8",
    )
