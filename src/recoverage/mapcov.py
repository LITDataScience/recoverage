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
    index = CoverageIndex(coverage.files)
    mapped: list[MappedFunction] = []
    for structure in structures:
        file_cov = index.match(structure.path)
        lines = index.lines(file_cov) if file_cov is not None else None
        for function in structure.functions:
            mapped.append(_map_function(function, file_cov, coverage.measured, lines))
    return mapped


def module_stats(structures: list[FileStructure], coverage: CoverageResult) -> list[ModuleStat]:
    index = CoverageIndex(coverage.files)
    stats: list[ModuleStat] = []
    for structure in structures:
        if structure.functions == [] and structure.statement_count == 0:
            continue
        match = index.match(structure.path) if coverage.measured else None
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


def _map_function(
    function,
    file_cov: FileCoverage | None,
    measured: bool,
    lines: tuple[frozenset[int], frozenset[int]] | None = None,
) -> MappedFunction:
    if not measured or file_cov is None:
        return MappedFunction(
            spec=function,
            coverage_ratio=0.0 if measured and file_cov is None else None,
            covered_lines=0,
            executable_lines=len(function.statement_lines) if measured else 0,
            missing_lines=list(function.statement_lines) if measured and file_cov is None else [],
            file_measured=file_cov is not None,
        )
    executed, missing = lines if lines is not None else _line_sets(file_cov)
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


def _line_sets(file_cov: FileCoverage) -> tuple[frozenset[int], frozenset[int]]:
    return frozenset(file_cov.executed_lines), frozenset(file_cov.missing_lines)


class CoverageIndex:
    """Exact-path lookup plus a basename bucket for the directory-bounded suffix rule.

    Build is O(F). A lookup is O(1) exact, or O(k) where k is the number of coverage
    files sharing the same basename, instead of O(F) per structure path. Line sets
    are materialised once per file, not once per function in that file.
    """

    def __init__(self, files: list[FileCoverage]):
        self.exact: dict[str, FileCoverage] = {}
        self.by_name: dict[str, list[str]] = {}
        self._lines: dict[str, tuple[frozenset[int], frozenset[int]]] = {}
        for item in files:
            self.exact[item.path] = item
            self.by_name.setdefault(item.path.rsplit("/", 1)[-1], []).append(item.path)

    def lines(self, file_cov: FileCoverage) -> tuple[frozenset[int], frozenset[int]]:
        found = self._lines.get(file_cov.path)
        if found is None:
            found = _line_sets(file_cov)
            self._lines[file_cov.path] = found
        return found

    def match(self, structure_path: str) -> FileCoverage | None:
        found = self.exact.get(structure_path)
        if found is not None:
            return found
        name = structure_path.rsplit("/", 1)[-1]
        hits = [
            key
            for key in self.by_name.get(name, ())
            if key.endswith("/" + structure_path) or structure_path.endswith("/" + key)
        ]
        if len(hits) == 1:
            return self.exact[hits[0]]
        return None


def match_coverage(structure_path: str, files: dict[str, FileCoverage]) -> FileCoverage | None:
    """Exact path, or the one key that is a directory-bounded suffix of the other."""
    return CoverageIndex(list(files.values())).match(structure_path)


def _match(structure_path: str, files: dict[str, FileCoverage]) -> FileCoverage | None:
    return match_coverage(structure_path, files)
