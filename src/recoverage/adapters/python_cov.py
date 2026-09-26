"""Run coverage.py and fold unimported source files into the project totals."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from recoverage.adapters.static import unmeasured
from recoverage.models import CoverageResult, FileCoverage, FileStructure, ProjectProfile
from recoverage.proc import child_env, run_tree


def run_python(
    profile: ProjectProfile,
    structures: list[FileStructure],
    output_dir: Path,
    *,
    timeout: int = 180,
) -> CoverageResult:
    from recoverage.host import TempSpaceError, assert_temp_space

    try:
        assert_temp_space()
    except TempSpaceError as exc:
        return unmeasured(profile, structures, notes=[str(exc)])
    work = Path(tempfile.mkdtemp(prefix="recoverage-cov-"))
    try:
        return _run_python(profile, structures, output_dir, work, timeout=timeout)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _run_python(
    profile: ProjectProfile,
    structures: list[FileStructure],
    output_dir: Path,
    work: Path,
    *,
    timeout: int = 180,
) -> CoverageResult:
    root = Path(profile.root)
    cov_file = work / ".coverage"
    json_path = work / "coverage.json"
    env = child_env(
        {
            "COVERAGE_FILE": str(cov_file),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": profile.import_root,
        }
    )
    source = ",".join(profile.packages) if profile.packages else _fallback_source(profile)
    command = [
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--branch",
        f"--source={source}",
        "-m",
        *(_runner_args(profile, output_dir)),
    ]
    try:
        completed = run_tree(command, cwd=str(root), env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        result = unmeasured(profile, structures, notes=[f"coverage.py timed out after {timeout}s."])
        result.command = command
        result.tests_exit_code = 124
        return result
    except OSError as exc:
        result = unmeasured(profile, structures, notes=[f"coverage.py failed to start: {exc}"])
        result.command = command
        return result

    if completed.returncode == 4:
        result = unmeasured(
            profile,
            structures,
            notes=[_pytest_exit_note(completed.stderr or "")],
            tool="coverage.py",
        )
        result.command = command
        result.tests_exit_code = 4
        return result

    json_cmd = [sys.executable, "-m", "coverage", "json", "-o", str(json_path), "--pretty-print"]
    json_run = subprocess.run(json_cmd, cwd=root, env=env, capture_output=True, text=True, check=False)
    notes = []
    if completed.returncode != 0:
        notes.append(
            f"Tests exited {completed.returncode}. Coverage data is still used when coverage.py wrote it."
        )
    if json_run.returncode != 0 or not json_path.is_file():
        detail = (json_run.stderr or json_run.stdout or "coverage json produced no file").strip()
        result = unmeasured(profile, structures, notes=[*notes, detail])
        result.command = command
        result.tests_exit_code = completed.returncode
        return result

    raw = json_path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    (output_dir / "coverage.json").write_text(raw, encoding="utf-8")
    files = _parse_files(payload, root)
    return _project_totals(
        profile,
        structures,
        files,
        payload.get("totals", {}),
        command,
        completed.returncode,
        notes,
    )


def _pytest_exit_note(stderr: str) -> str:
    """One sentence. The traceback itself is not stored."""
    if "unrecognized arguments" in stderr and "--cov" in stderr:
        return (
            "pytest exited 4 because a --cov flag in addopts is not available in this interpreter. "
            "Recoverage clears addopts and disables the cov plugin."
        )
    if "while loading conftest" in stderr or "No module named" in stderr:
        missing = re.search(r"No module named ['\"]([^'\"]+)['\"]", stderr)
        name = missing.group(1) if missing else "a project dependency"
        return (
            f"pytest exited 4 while importing the test configuration ({name} is not installed). "
            "The Python that is running Recoverage does not have this project's dependencies, so coverage was not measured. "
            "Run recoverage with that project's interpreter."
        )
    return "pytest exited 4 before tests ran, so coverage was not measured."


def _runner_args(profile: ProjectProfile, output_dir: Path) -> list[str]:
    if profile.test_runner == "unittest":
        return ["unittest", "discover", "-q"]
    cache = (output_dir / ".pytest_cache").as_posix()
    # Project addopts often include --cov. Under `coverage run` those flags are either
    # unrecognized (pytest exits 4) or a second coverage plugin. Clear them.
    return ["pytest", "-q", "--tb=line", "-p", "no:cov", "-o", "addopts=", "-o", f"cache_dir={cache}"]


def _fallback_source(profile: ProjectProfile) -> str:
    roots = {Path(path).parts[0] for path in profile.source_files if Path(path).parts}
    return ",".join(sorted(roots)) or "."


def _parse_files(payload: dict, root: Path) -> list[FileCoverage]:
    parsed: list[FileCoverage] = []
    for filename, info in payload.get("files", {}).items():
        summary = info.get("summary", {})
        num_branches = int(summary.get("num_branches") or 0)
        branch_percent = summary.get("percent_covered_branches")
        parsed.append(
            FileCoverage(
                path=_relative(root, filename),
                covered_lines=int(summary.get("covered_lines") or 0),
                num_statements=int(summary.get("num_statements") or 0),
                percent_covered=float(summary.get("percent_covered") or 0.0),
                covered_branches=int(summary.get("covered_branches") or 0),
                num_branches=num_branches,
                percent_covered_branches=float(branch_percent) if branch_percent is not None else None,
                executed_lines=[int(line) for line in info.get("executed_lines", [])],
                missing_lines=[int(line) for line in info.get("missing_lines", [])],
            )
        )
    return parsed


def _relative(root: Path, filename: str) -> str:
    path = Path(filename)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def _project_totals(
    profile: ProjectProfile,
    structures: list[FileStructure],
    files: list[FileCoverage],
    totals: dict,
    command: list[str],
    exit_code: int,
    notes: list[str],
) -> CoverageResult:
    by_path = {item.path: item for item in files}
    covered = 0
    statements = 0
    covered_branches = 0
    branches = 0
    missing_files = 0
    extra_static_branches = 0
    for structure in structures:
        if structure.language != "python":
            continue
        match = _match(structure.path, by_path)
        if match is None:
            missing_files += 1
            statements += structure.statement_count
            extra_static_branches += sum(function.branch_count for function in structure.functions)
            notes.append(f"{structure.path} was not imported during the test run; counted as uncovered.")
            continue
        covered += match.covered_lines
        statements += match.num_statements
        covered_branches += match.covered_branches
        branches += match.num_branches
    line_percent = round(100.0 * covered / statements, 2) if statements else None
    if missing_files == 0:
        branch_percent = _tool_branch(totals, branches, covered_branches)
        branch_is_tool = True
    else:
        denominator = branches + extra_static_branches
        branch_percent = round(100.0 * covered_branches / denominator, 2) if denominator else None
        branch_is_tool = False
        notes.append(
            "Branch percentage mixes coverage.py arcs on imported files with static decision "
            "points in files the tests never imported. That mix is heuristic."
        )
    tool_line = totals.get("percent_covered")
    tool_branch = totals.get("percent_covered_branches")
    return CoverageResult(
        tool="coverage.py",
        measured=True,
        tool_line_percent=round(float(tool_line), 2) if tool_line is not None else None,
        tool_branch_percent=round(float(tool_branch), 2) if tool_branch is not None else None,
        line_percent=line_percent,
        branch_percent=branch_percent,
        branch_is_tool=branch_is_tool,
        files=files,
        tests_exit_code=exit_code,
        notes=notes,
        command=command,
    )


def _tool_branch(totals: dict, branches: int, covered_branches: int) -> float | None:
    if totals.get("percent_covered_branches") is not None and int(totals.get("num_branches") or 0) == branches:
        return round(float(totals["percent_covered_branches"]), 2)
    if branches == 0:
        return 100.0
    return round(100.0 * covered_branches / branches, 2)


def _match(structure_path: str, files: dict[str, FileCoverage]) -> FileCoverage | None:
    from recoverage.mapcov import match_coverage

    return match_coverage(structure_path, files)
