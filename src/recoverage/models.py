"""JSON-friendly data records for a Recoverage run."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
GATES = ("blocked", "needs-review", "merge-ready", "production-ready")
GATE_RANK = {name: index for index, name in enumerate(GATES)}
RISK_THRESHOLD = 0.55


@dataclass
class FunctionSpec:
    name: str
    qualname: str
    file: str
    lineno: int
    end_lineno: int
    branch_count: int
    complexity: int
    is_public: bool
    risk_score: float
    risk_tags: list[str]
    parameters: list[str]
    is_method: bool = False
    statement_lines: list[int] = field(default_factory=list)


@dataclass
class FileStructure:
    path: str
    language: str
    package: str
    module: str
    line_count: int
    statement_count: int
    functions: list[FunctionSpec]
    parse_error: str | None = None


@dataclass
class FileCoverage:
    path: str
    covered_lines: int
    num_statements: int
    percent_covered: float
    covered_branches: int
    num_branches: int
    percent_covered_branches: float | None
    executed_lines: list[int]
    missing_lines: list[int]


@dataclass
class CoverageResult:
    tool: str
    measured: bool
    tool_line_percent: float | None
    tool_branch_percent: float | None
    line_percent: float | None
    branch_percent: float | None
    branch_is_tool: bool
    files: list[FileCoverage]
    tests_exit_code: int | None
    notes: list[str]
    command: list[str]


@dataclass
class MappedFunction:
    spec: FunctionSpec
    coverage_ratio: float | None
    covered_lines: int
    executable_lines: int
    missing_lines: list[int]
    file_measured: bool


@dataclass
class ModuleStat:
    name: str
    line_percent: float | None
    statements: int
    covered: int


@dataclass
class Hotspot:
    qualname: str
    file: str
    risk_score: float
    coverage_ratio: float | None
    risk_tags: list[str]


@dataclass
class Gap:
    id: str
    severity: str
    kind: str
    title: str
    why: str
    file: str
    symbol: str | None
    suggestion: str
    heuristic: bool
    llm_enriched: bool = False


@dataclass
class ScoreFactor:
    id: str
    title: str
    earned: float
    maximum: float
    detail: str
    heuristic: bool


@dataclass
class ScoreResult:
    score: float
    gate: str
    factors: list[ScoreFactor]
    mutation_testing_ran: bool
    notes: list[str]


@dataclass
class ProjectProfile:
    root: str
    primary_language: str
    languages: list[str]
    test_runner: str | None
    coverage_tool: str | None
    test_files: list[str]
    source_files: list[str]
    entry_points: list[str]
    packages: list[str]
    import_root: str
    src_layout: bool
    flake_markers: list[str]


@dataclass
class Analysis:
    version: str
    generated_at: str
    llm: str
    project: ProjectProfile
    coverage: CoverageResult
    functions: list[MappedFunction]
    modules: list[ModuleStat]
    hotspots: list[Hotspot]
    gaps: list[Gap]
    score: ScoreResult
    analytics: dict = field(default_factory=dict)


def _from_dict(cls: type, data: dict[str, Any]) -> Any:
    return cls(**data)


def analysis_to_dict(analysis: Analysis) -> dict[str, Any]:
    return asdict(analysis)


def analysis_from_dict(data: dict[str, Any]) -> Analysis:
    project = ProjectProfile(**data["project"])
    coverage = CoverageResult(
        **{
            **data["coverage"],
            "files": [FileCoverage(**item) for item in data["coverage"]["files"]],
        }
    )
    functions = [
        MappedFunction(
            spec=FunctionSpec(**item["spec"]),
            coverage_ratio=item["coverage_ratio"],
            covered_lines=item["covered_lines"],
            executable_lines=item["executable_lines"],
            missing_lines=item["missing_lines"],
            file_measured=item["file_measured"],
        )
        for item in data["functions"]
    ]
    return Analysis(
        version=data["version"],
        generated_at=data["generated_at"],
        llm=data["llm"],
        project=project,
        coverage=coverage,
        functions=functions,
        modules=[ModuleStat(**item) for item in data["modules"]],
        hotspots=[Hotspot(**item) for item in data["hotspots"]],
        gaps=[Gap(**item) for item in data["gaps"]],
        score=ScoreResult(
            **{
                **data["score"],
                "factors": [ScoreFactor(**item) for item in data["score"]["factors"]],
            }
        ),
        analytics=data.get("analytics") or {},
    )
