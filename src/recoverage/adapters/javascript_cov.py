"""Run c8 or istanbul/nyc when one of them is installed. No npm installs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from recoverage.adapters.static import unmeasured
from recoverage.models import CoverageResult, FileCoverage, FileStructure, ProjectProfile


def run_javascript(
    profile: ProjectProfile,
    structures: list[FileStructure],
    output_dir: Path,
) -> CoverageResult:
    tool = profile.coverage_tool or ""
    report_dir = output_dir / "js-coverage"
    report_dir.mkdir(parents=True, exist_ok=True)
    test_cmd = _test_command(profile)
    if tool == "c8":
        command = ["npx", "--no-install", "c8", "--reporter=json", "--report-dir", str(report_dir), *test_cmd]
    elif tool == "istanbul":
        command = ["npx", "--no-install", "nyc", "--reporter=json", "--report-dir", str(report_dir), *test_cmd]
    else:
        return unmeasured(profile, structures, notes=[f"Unsupported JS coverage tool: {tool}"])
    try:
        completed = subprocess.run(
            command,
            cwd=profile.root,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result = unmeasured(profile, structures, notes=[f"{tool} did not finish: {exc}"], tool=tool)
        result.command = command
        return result
    payload_path = _find_istanbul_json(report_dir)
    if payload_path is None:
        tail = (completed.stdout + "\n" + completed.stderr).strip().splitlines()
        result = unmeasured(
            profile,
            structures,
            notes=[f"{tool} produced no coverage JSON.", " ".join(tail[-4:])],
            tool=tool,
        )
        result.command = command
        result.tests_exit_code = completed.returncode
        return result
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    files = parse_istanbul(payload, Path(profile.root))
    return _totals(profile, structures, files, command, completed.returncode, tool)


def parse_istanbul(payload: dict, root: Path) -> list[FileCoverage]:
    """Parse Istanbul/c8 coverage-final.json. Statement hits are `s`, branch hits are `b`."""
    files: list[FileCoverage] = []
    for filename, info in payload.items():
        if not isinstance(info, dict) or "s" not in info:
            continue
        statements: dict = info.get("s") or {}
        executed = sum(1 for hits in statements.values() if int(hits) > 0)
        total = len(statements)
        branches = info.get("b") or {}
        branch_slots = 0
        branch_hits = 0
        for pair in branches.values():
            if isinstance(pair, list):
                branch_slots += len(pair)
                branch_hits += sum(1 for hits in pair if int(hits) > 0)
        statement_map = info.get("statementMap") or {}
        executed_lines: list[int] = []
        missing_lines: list[int] = []
        for key, hits in statements.items():
            location = statement_map.get(key) or statement_map.get(str(key)) or {}
            start = (location.get("start") or {}).get("line")
            if not isinstance(start, int):
                continue
            if int(hits) > 0:
                executed_lines.append(start)
            else:
                missing_lines.append(start)
        percent = round(100.0 * executed / total, 2) if total else 100.0
        branch_percent = round(100.0 * branch_hits / branch_slots, 2) if branch_slots else None
        path = Path(info.get("path") or filename)
        if path.is_absolute():
            try:
                relative = path.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                relative = path.as_posix()
        else:
            relative = path.as_posix()
        files.append(
            FileCoverage(
                path=relative,
                covered_lines=executed,
                num_statements=total,
                percent_covered=percent,
                covered_branches=branch_hits,
                num_branches=branch_slots,
                percent_covered_branches=branch_percent,
                executed_lines=sorted(set(executed_lines)),
                missing_lines=sorted(set(missing_lines)),
            )
        )
    return files


def _find_istanbul_json(report_dir: Path) -> Path | None:
    for name in ("coverage-final.json", "coverage-summary.json"):
        candidate = report_dir / name
        if candidate.is_file() and name.endswith("final.json"):
            return candidate
    matches = sorted(report_dir.glob("*.json"))
    for match in matches:
        if "final" in match.name:
            return match
    return matches[0] if matches else None


def _test_command(profile: ProjectProfile) -> list[str]:
    if profile.test_runner == "vitest":
        return ["npx", "--no-install", "vitest", "run"]
    return ["npx", "--no-install", "jest", "--runInBand"]


def _totals(
    profile: ProjectProfile,
    structures: list[FileStructure],
    files: list[FileCoverage],
    command: list[str],
    exit_code: int,
    tool: str,
) -> CoverageResult:
    del profile
    by_path = {item.path: item for item in files}
    covered = statements = covered_branches = branches = 0
    missing = 0
    extra_branches = 0
    notes: list[str] = []
    if exit_code != 0:
        notes.append(f"JS tests exited {exit_code}.")
    for structure in structures:
        if structure.language not in {"javascript", "typescript"}:
            continue
        match = by_path.get(structure.path)
        if match is None:
            missing += 1
            statements += structure.statement_count
            extra_branches += sum(function.branch_count for function in structure.functions)
            notes.append(f"{structure.path} was not in the {tool} report; counted as uncovered.")
            continue
        covered += match.covered_lines
        statements += match.num_statements
        covered_branches += match.covered_branches
        branches += match.num_branches
    line_percent = round(100.0 * covered / statements, 2) if statements else None
    if missing == 0:
        branch_percent = round(100.0 * covered_branches / branches, 2) if branches else 100.0
        branch_is_tool = True
    else:
        denominator = branches + extra_branches
        branch_percent = round(100.0 * covered_branches / denominator, 2) if denominator else None
        branch_is_tool = False
        notes.append("Branch percentage includes heuristic static decisions for files missing from the JS report.")
    tool_line = round(100.0 * sum(item.covered_lines for item in files) / sum(item.num_statements for item in files), 2) if files and sum(item.num_statements for item in files) else None
    return CoverageResult(
        tool=tool,
        measured=True,
        tool_line_percent=tool_line,
        tool_branch_percent=round(100.0 * covered_branches / branches, 2) if branches else None,
        line_percent=line_percent,
        branch_percent=branch_percent,
        branch_is_tool=branch_is_tool,
        files=files,
        tests_exit_code=exit_code,
        notes=notes,
        command=command,
    )
