from __future__ import annotations

from recoverage.models import CoverageResult, FileStructure, ProjectProfile


def unmeasured(
    profile: ProjectProfile,
    structures: list[FileStructure],
    *,
    notes: list[str] | None = None,
    tool: str = "static",
) -> CoverageResult:
    del profile, structures
    return CoverageResult(
        tool=tool,
        measured=False,
        tool_line_percent=None,
        tool_branch_percent=None,
        line_percent=None,
        branch_percent=None,
        branch_is_tool=False,
        files=[],
        tests_exit_code=None,
        notes=list(notes or ["Runtime coverage was not measured."]),
        command=[],
    )
