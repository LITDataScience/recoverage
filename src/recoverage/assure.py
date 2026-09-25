"""Sandbox, four filters, and at most three auto-fix retries. Then copy survivors back."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from recoverage.generate import PlannedTest
from recoverage.proc import child_env, run_tree, temp_copy
from recoverage.models import Analysis
from recoverage.mutate import mutate_function_source


def assure_and_write(analysis: Analysis, planned: list[tuple[str, str]], *, dry_run: bool) -> tuple[list[PlannedTest], list[dict]]:
    trace: list[dict] = []
    if not planned:
        trace.append({"agent": "tester", "action": "no-drafts"})
        return [], trace
    if dry_run:
        trace.append({"agent": "tester", "action": "dry-run", "files": [path for path, _content in planned]})
        return [PlannedTest(path=path, content=content, action="dry-run") for path, content in planned], trace
    root = Path(analysis.project.root).resolve()
    parent, sandbox = temp_copy(root, prefix="recoverage-sandbox-")
    written: list[Path] = []
    try:
        for relative, content in planned:
            target = _allocate(sandbox, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(target)
        passed = False
        for attempt in range(3):
            ok, detail = _filters(sandbox, analysis, written)
            trace.append({"agent": "tester", "attempt": attempt + 1, **detail})
            if ok:
                passed = True
                break
            fixed = _autofix(written, detail.get("output", ""))
            trace.append({"agent": "auto-fix", "attempt": attempt + 1, "removed": fixed})
            if not fixed:
                break
        survivors: list[PlannedTest] = []
        if passed:
            for path in written:
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8")
                if "def test_" not in text:
                    continue
                relative = path.relative_to(sandbox).as_posix()
                destination = _allocate(root, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise FileExistsError(f"refusing to overwrite {destination}")
                destination.write_text(text, encoding="utf-8")
                survivors.append(PlannedTest(path=destination.relative_to(root).as_posix(), content=text, action="write"))
        trace.append({"agent": "tester", "action": "committed" if survivors else "discarded", "count": len(survivors)})
        return survivors, trace
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def _filters(sandbox: Path, analysis: Analysis, files: list[Path]) -> tuple[bool, dict]:
    for path in files:
        if not path.is_file():
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            return False, {"stage": "compile", "output": f"{path.name}: {exc}"}
    before = sum(item.covered_lines for item in analysis.coverage.files)
    codes = []
    output = ""
    for run_index in range(5):
        completed = _pytest(sandbox, analysis)
        codes.append(completed.returncode)
        output = (completed.stdout + "\n" + completed.stderr)[-4000:]
        if completed.returncode != 0:
            return False, {"stage": "flakiness" if run_index else "execution", "output": output, "runs": codes}
    after = _covered_lines(sandbox, analysis)
    novel = (not analysis.coverage.measured) or after > before
    newly_killed = 0 if novel else _newly_killed(sandbox, analysis)
    reason = acceptance(novel, newly_killed)
    if reason is None:
        return False, {
            "stage": "novel-coverage",
            "output": f"covered lines {before} -> {after}; newly killed mutants {newly_killed}",
            "runs": codes,
        }
    return True, {
        "stage": "passed",
        "acceptance": reason,
        "output": output,
        "runs": codes,
        "covered_before": before,
        "covered_after": after,
        "newly_killed": newly_killed,
    }


def acceptance(novel: bool, newly_killed: int) -> str | None:
    """Keep a draft that adds lines or kills a mutant the current suite left alive.

    A coverage increase alone is the coverage illusion when the assertion cannot fail.
    A kill on an already-covered path is still evidence, which is the ACH filter.
    """
    if novel:
        return "novel-coverage"
    if newly_killed > 0:
        return "mutant-kill"
    return None


def _newly_killed(sandbox: Path, analysis: Analysis) -> int:
    mutation = (analysis.analytics or {}).get("mutation") or {}
    survivors = [item for item in mutation.get("mutants") or [] if not item.get("killed")]
    killed = 0
    for mutant in survivors[:5]:
        path = sandbox / mutant["file"]
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        mutated, _description = mutate_function_source(original, str(mutant["symbol"]).split(".")[-1])
        if mutated is None:
            continue
        path.write_text(mutated, encoding="utf-8")
        try:
            code = _pytest(sandbox, analysis).returncode
        finally:
            path.write_text(original, encoding="utf-8")
        if code != 0:
            killed += 1
    return killed


def _autofix(files: list[Path], output: str) -> int:
    removed = 0
    names = _failed_names(output)
    for path in list(files):
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            path.unlink()
            removed += 1
            continue
        if not isinstance(tree, ast.Module):
            continue
        kept = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                removed += 1
                continue
            kept.append(node)
        if removed and len(kept) != len(tree.body):
            tree.body = kept
            if not any(isinstance(node, ast.FunctionDef) for node in tree.body):
                path.unlink()
            else:
                path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
    return removed


def _failed_names(output: str) -> set[str]:
    names = set()
    for line in output.splitlines():
        if "::" in line and "test_" in line:
            tail = line.split("::")[-1]
            name = tail.split()[0].strip()
            if name.startswith("test_"):
                names.add(name)
    return names


def _pytest(sandbox: Path, analysis: Analysis) -> subprocess.CompletedProcess:
    env = child_env({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": _sandbox_import(sandbox, analysis)})
    try:
        return run_tree(
            [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider"],
            cwd=str(sandbox),
            env=env,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(["pytest"], 124, "", "timeout")


def _covered_lines(sandbox: Path, analysis: Analysis) -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["COVERAGE_FILE"] = str(sandbox / ".coverage")
    env["PYTHONPATH"] = _sandbox_import(sandbox, analysis)
    source = ",".join(analysis.project.packages) or "."
    subprocess.run(
        [sys.executable, "-m", "coverage", "run", f"--source={source}", "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider"],
        cwd=sandbox,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    json_path = sandbox / "coverage.json"
    subprocess.run(
        [sys.executable, "-m", "coverage", "json", "-o", str(json_path)],
        cwd=sandbox,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if not json_path.is_file():
        return 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    return int(payload.get("totals", {}).get("covered_lines") or 0)


def _sandbox_import(sandbox: Path, analysis: Analysis) -> str:
    import_root = Path(analysis.project.import_root)
    try:
        relative = import_root.resolve().relative_to(Path(analysis.project.root).resolve())
    except ValueError:
        return str(import_root)
    return str(sandbox / relative)


def _allocate(root: Path, relative: str) -> Path:
    path = Path(relative)
    candidate = root / path
    number = 2
    while candidate.exists():
        candidate = root / path.with_name(f"{path.stem}_{number}{path.suffix}")
        number += 1
    return candidate
