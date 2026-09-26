"""Runtime coverage adapters. The static adapter reports that nothing was measured."""

from __future__ import annotations

from pathlib import Path

from recoverage.adapters.javascript_cov import run_javascript
from recoverage.adapters.python_cov import run_python
from recoverage.adapters.static import unmeasured
from recoverage.models import CoverageResult, FileStructure, ProjectProfile


def collect_coverage(
    profile: ProjectProfile,
    structures: list[FileStructure],
    output_dir: Path,
    *,
    timeout: int = 180,
) -> CoverageResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    if profile.primary_language == "python" and profile.test_runner:
        return run_python(profile, structures, output_dir, timeout=timeout)
    if profile.primary_language in {"javascript", "typescript"} and profile.test_runner and profile.coverage_tool:
        return run_javascript(profile, structures, output_dir, timeout=timeout)
    notes = []
    if profile.primary_language in {"javascript", "typescript"} and not profile.coverage_tool:
        notes.append("Neither c8 nor istanbul/nyc is installed. Static structure analysis only.")
    if not profile.test_runner:
        notes.append("No test runner detected, so runtime coverage was not started.")
    if profile.primary_language not in {"python", "javascript", "typescript"}:
        notes.append(
            f"No runtime coverage adapter for {profile.primary_language}. Static structure analysis only."
        )
    return unmeasured(profile, structures, notes=notes)
