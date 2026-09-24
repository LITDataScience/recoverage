"""Join static structure with runtime line hits."""

from __future__ import annotations

from recoverage.models import (
    CoverageResult,
    FileCoverage,
    FileStructure,
    Hotspot,
    MappedFunction,
    ModuleStat,
)


def map_coverage(structures: list[FileStructure], coverage: CoverageResult) -> list[MappedFunction]:
    files = {item.path: item for item in coverage.files}
    mapped: list[MappedFunction] = []
    for structure in structures:
        file_cov = _match(structure.path, files)
        for function in structure.functions:
            mapped.append(_map_function(function, file_cov, coverage.measured))
    return mapped


def module_stats(structures: list[FileStructure], coverage: CoverageResult) -> list[ModuleStat]:
    files = {item.path: item for item in coverage.files}
    stats: list[ModuleStat] = []
    for structure in structures:
        if structure.functions == [] and structure.statement_count == 0:
            continue
        match = _match(structure.path, files) if coverage.measured else None
        if match is None:
            stats.append(
                ModuleStat(
                    name=structure.module or structure.path,
                    line_percent=0.0 if coverage.measured else None,
                    statements=structure.statement_count,
                    covered=0,
                )
            )
            continue
        percent = round(100.0 * match.covered_lines / match.num_statements, 2) if match.num_statements else 100.0
        stats.append(
            ModuleStat(
                name=structure.module or structure.path,
                line_percent=percent,
                statements=match.num_statements,
                covered=match.covered_lines,
            )
        )
    return stats


def hotspots(functions: list[MappedFunction], limit: int = 8) -> list[Hotspot]:
    ranked = sorted(functions, key=lambda item: (-item.spec.risk_score, item.spec.qualname))
    chosen = [item for item in ranked if item.spec.risk_score > 0][:limit]
    if not chosen:
        chosen = ranked[: min(limit, len(ranked))]
    return [
        Hotspot(
            qualname=item.spec.qualname,
            file=item.spec.file,
            risk_score=item.spec.risk_score,
            coverage_ratio=item.coverage_ratio,
            risk_tags=list(item.spec.risk_tags),
        )
        for item in chosen
    ]


def _map_function(function, file_cov: FileCoverage | None, measured: bool) -> MappedFunction:
    if not measured or file_cov is None:
        return MappedFunction(
            spec=function,
            coverage_ratio=0.0 if measured and file_cov is None else None,
            covered_lines=0,
            executable_lines=len(function.statement_lines) if measured else 0,
            missing_lines=list(function.statement_lines) if measured and file_cov is None else [],
            file_measured=file_cov is not None,
        )
    executed = set(file_cov.executed_lines)
    missing = set(file_cov.missing_lines)
    known = executed | missing
    in_function = [line for line in function.statement_lines if line in known]
    if not in_function:
        # Definition ran (imported) but coverage.py reported no statements inside.
        # Treat a file that was measured and has no missing lines in range as covered.
        span = set(range(function.lineno, function.end_lineno + 1))
        missed = sorted(span & missing)
        hit = sorted(span & executed)
        if not hit and not missed:
            ratio = 1.0 if function.lineno in executed or not known else None
            return MappedFunction(
                spec=function,
                coverage_ratio=ratio,
                covered_lines=0,
                executable_lines=0,
                missing_lines=[],
                file_measured=True,
            )
        total = len(hit) + len(missed)
        return MappedFunction(
            spec=function,
            coverage_ratio=round(len(hit) / total, 4) if total else None,
            covered_lines=len(hit),
            executable_lines=total,
            missing_lines=missed,
            file_measured=True,
        )
    hit_lines = [line for line in in_function if line in executed]
    miss_lines = [line for line in in_function if line in missing]
    total = len(hit_lines) + len(miss_lines)
    return MappedFunction(
        spec=function,
        coverage_ratio=round(len(hit_lines) / total, 4) if total else None,
        covered_lines=len(hit_lines),
        executable_lines=total,
        missing_lines=miss_lines,
        file_measured=True,
    )


def _match(structure_path: str, files: dict[str, FileCoverage]) -> FileCoverage | None:
    if structure_path in files:
        return files[structure_path]
    for key, item in files.items():
        if structure_path.endswith(key) or key.endswith(structure_path):
            return item
    return None
