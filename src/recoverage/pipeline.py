"""Discover, measure, score, and write reports."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from recoverage.version import __version__
from recoverage.adapters import collect_coverage
from recoverage.adapters.static import unmeasured
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
from recoverage.models import Analysis, analysis_to_dict, load_analysis
from recoverage.mutate import run_mutants
from recoverage.pbt import run_properties
from recoverage.perf import time_functions
from recoverage.privacy import scrub
from recoverage.report import write_reports
from recoverage.sbst import search
from recoverage.score import meets_threshold, score_project
from recoverage.sources import SourceCache
from recoverage.structure import analyze_project, attach_sources


_RUN_BUDGET_S = 600


def run_analysis(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "off",
    client=None,
    dynamic: bool = False,
    deep: bool = False,
) -> Analysis:
    if deep:
        dynamic = True
    started = time.monotonic()
    profile = discover(path)
    cache = SourceCache(Path(profile.root))
    structures = analyze_project(profile, cache)
    attach_sources(structures, Path(profile.root), cache)
    output_dir.mkdir(parents=True, exist_ok=True)
    if dynamic and time.monotonic() - started > _RUN_BUDGET_S:
        coverage = unmeasured(
            profile,
            structures,
            notes=[f"Run budget of {_RUN_BUDGET_S}s was spent before tests. Coverage was not measured."],
        )
    elif dynamic:
        coverage = collect_coverage(profile, structures, output_dir)
    else:
        coverage = unmeasured(
            profile,
            structures,
            notes=["Static-only mode. Project code was not imported and no test runner was started. Pass --dynamic to opt in."],
        )
    functions = map_coverage(structures, coverage)
    modules = module_stats(structures, coverage)
    spots = hotspots(functions)
    extra = parse_error_gaps(
        [(item.path, item.parse_error) for item in structures if item.parse_error]
    )
    gaps = find_gaps(profile, functions, extra, cache=cache)
    llm_client = client if client is not None else client_from_env(mode=llm_mode)
    gaps, llm_name = enrich_gaps(gaps, llm_client)
    if llm_mode == "off":
        llm_name = "off"
    graph = index_project(profile)
    if deep and time.monotonic() - started > _RUN_BUDGET_S:
        note = f"Run budget of {_RUN_BUDGET_S}s was spent before deep probes."
        pbt = {"ran": False, "trials": 0, "passed": 0, "failed": 0, "note": note}
        mutation = {"ran": False, "killed": 0, "total": 0, "mutants": [], "note": note}
        timing = {"ran": False, "regression": False, "note": note}
        sbst = {"cases": [], "stalls": 0, "agents": [], "llm": False}
    elif deep:
        pbt = run_properties(profile, functions)
        mutation = run_mutants(profile, functions)
        timing = time_functions(profile, functions)
        sbst = search(profile, functions, client=llm_client)
    else:
        pbt = {"ran": False, "trials": 0, "passed": 0, "failed": 0, "note": "Deep probes were not requested."}
        mutation = {"ran": False, "killed": 0, "total": 0, "mutants": [], "note": "Mutation testing did not run."}
        timing = {"ran": False, "regression": False, "note": "Timing was not measured."}
        sbst = {"cases": [], "stalls": 0, "agents": [], "llm": False}
    prompt = prompt_coverage(profile, graph, cache=cache)
    blast = blast_radius(graph, functions, coverage)
    audit = attach_measurements(
        audit_project(profile, functions, cache=cache),
        line_percent=coverage.line_percent,
        branch_percent=coverage.branch_percent,
        measured=coverage.measured,
        mutation=mutation,
    )
    analytics = _analytics(graph, pbt, mutation, prompt, blast, timing, sbst, audit)
    score = score_project(profile, coverage, functions, gaps, analytics)
    cache.clear()
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


_LOCK = threading.Lock()


def _enter():
    if not _LOCK.acquire(blocking=False):
        raise RuntimeError("recoverage is already running in this process")


def _leave() -> None:
    _LOCK.release()


def execute_run(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "off",
    threshold: str | None = None,
    client=None,
    dynamic: bool = False,
    deep: bool = False,
) -> tuple[Analysis, int]:
    _enter()
    try:
        analysis = run_analysis(path, output_dir, llm_mode=llm_mode, client=client, dynamic=dynamic, deep=deep)
        write_analysis_reports(analysis, output_dir)
        ok = meets_threshold(analysis.score, threshold)
        return analysis, 0 if ok else 1
    finally:
        _leave()


def execute_report(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "off",
    threshold: str | None = None,
    analysis_path: Path | None = None,
    dynamic: bool = False,
    deep: bool = False,
) -> tuple[Analysis, int]:
    _enter()
    try:
        return _execute_report(
            path,
            output_dir,
            llm_mode=llm_mode,
            threshold=threshold,
            analysis_path=analysis_path,
            dynamic=dynamic,
            deep=deep,
        )
    finally:
        _leave()


def _execute_report(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "off",
    threshold: str | None = None,
    analysis_path: Path | None = None,
    dynamic: bool = False,
    deep: bool = False,
) -> tuple[Analysis, int]:
    source = analysis_path or (output_dir / "analysis.json")
    if source.is_file():
        analysis = load_analysis(source)
    else:
        analysis = run_analysis(path, output_dir, llm_mode=llm_mode, dynamic=dynamic, deep=deep)
    write_analysis_reports(analysis, output_dir)
    return analysis, 0 if meets_threshold(analysis.score, threshold) else 1


def execute_generate(
    path: Path,
    output_dir: Path,
    *,
    llm_mode: str = "off",
    dry_run: bool = False,
    client=None,
    dynamic: bool = False,
    deep: bool = False,
) -> tuple[Analysis, list[PlannedTest]]:
    resolved = Path(path).resolve()
    analysis_path = output_dir / "analysis.json"
    if analysis_path.is_file():
        analysis = load_analysis(analysis_path)
    else:
        analysis = run_analysis(path, output_dir, llm_mode=llm_mode, client=client, dynamic=dynamic, deep=deep)
    analysis.project.root = str(resolved)
    if analysis.project.src_layout:
        analysis.project.import_root = str(resolved / "src")
    else:
        analysis.project.import_root = str(resolved)
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
    # One pass to group symbols by community. The previous list comprehension per community was O(C·V).
    grouped: dict[int, list[str]] = {}
    for symbol, cid in graph.communities.items():
        grouped.setdefault(cid, []).append(symbol)
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
                    "docstring": "",
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
            "communities": [{"id": community, "symbols": grouped[community]} for community in sorted(grouped)],
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
    payload = scrub(analysis_to_dict(analysis))
    # Compact output uses the C encoder; `indent=` falls back to the pure-Python one and
    # writes one line per statement number. `python -m json.tool` pretty-prints on demand.
    (output_dir / "analysis.json").write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
