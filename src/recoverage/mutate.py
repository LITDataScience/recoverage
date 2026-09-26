"""Real mutants on a temp copy. User source is not modified."""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

from recoverage.models import MappedFunction, ProjectProfile
from recoverage.proc import child_env, run_tree, temp_copy


def run_mutants(profile: ProjectProfile, functions: list[MappedFunction], *, limit: int = 5) -> dict:
    if profile.primary_language != "python" or not profile.test_runner:
        return {"ran": False, "killed": 0, "total": 0, "mutants": [], "note": "Mutation testing was not run."}
    root = Path(profile.root)
    covered = [item for item in functions if item.spec.is_public and item.file_measured and item.spec.file.endswith(".py")]
    uncovered = [item for item in functions if item.spec.is_public and item.coverage_ratio == 0 and item.spec.file.endswith(".py")]
    chosen = (covered + uncovered)[:limit]
    if not chosen:
        return {"ran": False, "killed": 0, "total": 0, "mutants": [], "note": "No functions to mutate."}
    from recoverage.host import TempSpaceError

    try:
        parent, sandbox = temp_copy(root, prefix="recoverage-mutants-")
    except TempSpaceError as exc:
        return {"ran": False, "killed": 0, "total": 0, "mutants": [], "note": str(exc)}
    mutants = []
    unviable = 0
    try:
        baseline = _pytest(sandbox, profile)
        if baseline != 0:
            return {
                "ran": True,
                "killed": 0,
                "timeouts": 0,
                "unviable": 0,
                "total": 0,
                "msi": None,
                "msi_total": None,
                "mutants": [],
                "note": f"Baseline tests already exit {baseline}. Kill counts would be meaningless, so no mutant was scored.",
            }
        for function in chosen:
            relative = function.spec.file
            original = (sandbox / relative).read_text(encoding="utf-8")
            mutated, description = mutate_function_source(original, function.spec.name)
            if mutated is None:
                unviable += 1
                continue
            (sandbox / relative).write_text(mutated, encoding="utf-8")
            code = _pytest(sandbox, profile)
            timed_out = code == "timeout"
            killed = timed_out or code != 0
            mutants.append(
                {
                    "symbol": function.spec.qualname,
                    "file": relative,
                    "operator": description,
                    "killed": killed,
                    "timeout": timed_out,
                    "exit_code": None if timed_out else code,
                }
            )
            (sandbox / relative).write_text(original, encoding="utf-8")
    finally:
        shutil.rmtree(parent, ignore_errors=True)
    killed = sum(1 for item in mutants if item["killed"])
    timeouts = sum(1 for item in mutants if item["timeout"])
    viable = len(mutants)
    pool = viable + unviable
    msi = None if viable == 0 else round(100.0 * killed / viable, 1)
    msi_total = None if pool == 0 else round(100.0 * killed / pool, 1)
    return {
        "ran": True,
        "killed": killed,
        "timeouts": timeouts,
        "unviable": unviable,
        "total": pool,
        "msi": msi,
        "msi_total": msi_total,
        "mutants": mutants,
        "note": (
            f"Killed {killed}/{viable} viable mutants on a temp copy"
            f" ({timeouts} timeouts counted as killed, {unviable} unviable excluded). "
            f"MSI {msi if msi is not None else 'n/a'}. "
            f"MSI_total {msi_total if msi_total is not None else 'n/a'} keeps unviable mutants in the denominator. "
            "This is a sampled operator flip, not a mutmut or cosmic-ray campaign. Project files were not edited."
        ),
    }


def mutate_function_source(source: str, function_name: str) -> tuple[str | None, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None, ""
    target = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            target = node
            break
    if target is None:
        return None, ""
    description = ""

    class Flip(ast.NodeTransformer):
        def __init__(self):
            self.done = False

        def visit_UnaryOp(self, node: ast.UnaryOp):
            if not self.done and isinstance(node.op, ast.Not):
                self.done = True
                return node.operand
            return self.generic_visit(node)

        def visit_Compare(self, node: ast.Compare):
            if self.done or not node.ops:
                return self.generic_visit(node)
            self.done = True
            node.ops = [ast.Gt() if isinstance(node.ops[0], ast.Lt) else ast.NotEq()]
            return node

    flip = Flip()
    flip.visit(target)
    if not flip.done:
        return None, ""
    description = f"operator replacement inside {function_name}"
    ast.fix_missing_locations(tree)
    return ast.unparse(tree), description


def _pytest(sandbox: Path, profile: ProjectProfile) -> int | str:
    import_root = Path(profile.import_root)
    try:
        relative_import = import_root.resolve().relative_to(Path(profile.root).resolve())
        sandbox_import = str(sandbox / relative_import)
    except ValueError:
        sandbox_import = str(import_root)
    env = child_env({"PYTHONPATH": sandbox_import, "PYTHONDONTWRITEBYTECODE": "1"})
    command = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider"]
    try:
        completed = run_tree(command, cwd=str(sandbox), env=env, timeout=120)
    except subprocess.TimeoutExpired:
        return "timeout"
    return completed.returncode
