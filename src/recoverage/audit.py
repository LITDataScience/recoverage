"""Authenticity measurements that stay outside the Merge Readiness Score.

CRAP, assertion strength, local dependency resolution, and a static flakiness
scan. Registry lookups are intentionally absent: default runs do not use the network.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

from recoverage.models import MappedFunction, ProjectProfile
from recoverage.sources import SourceCache
from recoverage.structure import iter_statements

_STDLIB = set(getattr(sys, "stdlib_module_names", ()))


def crap(complexity: int, coverage: float | None) -> float:
    """CRAP(m) = comp(m)^2 * (1 - cov(m))^3 + comp(m). Missing coverage counts as 0."""
    cov = 0.0 if coverage is None else min(1.0, max(0.0, coverage))
    return round((complexity**2) * ((1.0 - cov) ** 3) + complexity, 2)


def audit_project(profile: ProjectProfile, functions: list[MappedFunction], *, cache: SourceCache | None = None) -> dict:
    cache = cache or SourceCache(Path(profile.root))
    resolver = _Resolver(profile, cache)
    crap_report = _crap(functions)
    assertions = _assertions(profile, cache)
    authenticity = _authenticity(profile, resolver)
    flakiness = _firi(profile, cache)
    return {
        "crap": crap_report,
        "assertions": assertions,
        "authenticity": authenticity,
        "flakiness": flakiness,
        "scorecard": _scorecard(crap_report, assertions, authenticity, flakiness),
        "note": (
            "Authenticity scorecard is not the Merge Readiness Score and does not move the gate. "
            "DAR checks the workspace, the stdlib, and declared manifests. It does not query a package registry. "
            "FIRI is a static scan, not a reproduction of a flake."
        ),
    }


def _crap(functions: list[MappedFunction]) -> dict:
    rows = []
    for function in functions:
        if function.spec.name.startswith("_"):
            continue
        score = crap(function.spec.complexity, function.coverage_ratio)
        rows.append(
            {
                "symbol": function.spec.qualname,
                "file": function.spec.file,
                "complexity": function.spec.complexity,
                "coverage": None if function.coverage_ratio is None else round(function.coverage_ratio, 4),
                "crap": score,
                "over_30": score > 30,
            }
        )
    rows.sort(key=lambda item: -item["crap"])
    values = [item["crap"] for item in rows]
    mean = round(sum(values) / len(values), 2) if values else None
    hotspots = [item for item in rows if item["over_30"]]
    return {
        "mean": mean,
        "hotspots": hotspots[:12],
        "count_over_30": len(hotspots),
        "rows": rows[:12],
        "note": (
            "CRAP = complexity² × (1 − coverage)³ + complexity. "
            "Above 30 the function is a refactor-or-test target. Unmeasured coverage is treated as 0."
        ),
    }


def _assertions(profile: ProjectProfile, cache: SourceCache) -> dict:
    total = 0
    substantive = 0
    vacuous: list[dict] = []
    roulette = 0
    magic = 0
    aaa = 0
    for relative in profile.test_files:
        if not relative.endswith(".py"):
            continue
        tree = cache.tree(relative)
        if tree is None:
            continue
        for node in tree.body:
            targets = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                targets = [node]
            elif isinstance(node, ast.ClassDef):
                targets = [
                    child
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_")
                ]
            for function in targets:
                asserts = [child for child in ast.walk(function) if isinstance(child, ast.Assert)]
                if len(asserts) > 1 and all(item.msg is None for item in asserts):
                    roulette += 1
                if _aaa_violation(function):
                    aaa += 1
                for item in asserts:
                    total += 1
                    kind = _assert_kind(item)
                    if kind == "substantive":
                        substantive += 1
                    else:
                        vacuous.append({"file": relative, "line": item.lineno, "kind": kind})
                    if _magic_number(item):
                        magic += 1
    asr = None if total == 0 else round(100.0 * substantive / total, 1)
    return {
        "total": total,
        "substantive": substantive,
        "asr": asr,
        "vacuous": vacuous[:12],
        "assertion_roulette": roulette,
        "magic_numbers": magic,
        "aaa_violations": aaa,
        "note": (
            "ASR is substantive assertions divided by all assertions. "
            "Tautologies (x == x, assert True) and type-or-presence checks are not substantive. "
            "A comparison against a literal is substantive and can still be a magic-number smell."
        ),
    }


def _assert_kind(node: ast.Assert) -> str:
    test = node.test
    if isinstance(test, ast.Constant) and test.value is True:
        return "tautology"
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
        op = test.ops[0]
        left = ast.unparse(test.left)
        right = ast.unparse(test.comparators[0])
        if isinstance(op, (ast.Eq, ast.Is)) and left == right:
            return "tautology"
        if isinstance(op, (ast.IsNot, ast.NotEq)) and right == "None":
            return "vacuous"
        if isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)):
            return "substantive"
    if isinstance(test, ast.Call) and _call_name(test.func) in {"isinstance", "issubclass", "hasattr"}:
        return "vacuous"
    if isinstance(test, ast.Name):
        return "vacuous"
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        if isinstance(test.operand, ast.Constant):
            return "vacuous"
        return "substantive"
    return "substantive"


def _magic_number(node: ast.Assert) -> bool:
    for child in ast.walk(node.test):
        if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)) and not isinstance(child.value, bool):
            return True
    return False


def _aaa_violation(function: ast.AST) -> bool:
    seen_assert = False
    acted_after = False
    body = getattr(function, "body", [])
    for statement in body:
        if isinstance(statement, ast.Assert):
            if acted_after:
                return True
            seen_assert = True
        elif seen_assert and any(isinstance(child, ast.Call) for child in ast.walk(statement)):
            acted_after = True
    return False


class _Resolver:
    """Memoized module-file lookup and module export sets for one audit run.

    Without this every `from pkg.mod import name` re-stats up to four candidate
    paths and re-parses the target module. With it each module is resolved and
    parsed at most once per run.
    """

    def __init__(self, profile: ProjectProfile, cache: SourceCache):
        self.profile = profile
        self.cache = cache
        self._files: dict[str, str | None] = {}
        self._exports: dict[str, frozenset[str] | None] = {}

    def module_file(self, module: str) -> str | None:
        if module not in self._files:
            self._files[module] = _module_file(self.profile, module)
        return self._files[module]

    def symbol_defined(self, module: str, name: str) -> bool:
        relative = self.module_file(module)
        if relative is None:
            return True
        exports = self._exports.get(relative, ...)
        if exports is ...:
            tree = self.cache.tree(relative)
            exports = None if tree is None else _module_exports(tree)
            self._exports[relative] = exports
        return exports is not None and name in exports


def _module_exports(tree: ast.AST) -> frozenset[str]:
    names: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
    return frozenset(names)


def _authenticity(profile: ProjectProfile, resolver: _Resolver) -> dict:
    root = Path(profile.root)
    declared = _declared(root)
    local = _local_tops(profile)
    verified = 0
    total = 0
    phantoms: list[dict] = []
    unresolved: list[dict] = []
    for relative in [*profile.source_files, *profile.test_files]:
        path = root / relative
        if relative.endswith(".py"):
            found = _python_imports(path, relative, resolver, local, declared)
        elif relative.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
            text = resolver.cache.text(relative)
            if text is None:
                continue
            found = _js_imports(text, relative, declared)
        else:
            continue
        for item in found:
            total += 1
            if item["status"] == "verified":
                verified += 1
            elif item["status"] == "phantom":
                phantoms.append(item)
            else:
                unresolved.append(item)
    dar = None if total == 0 else round(100.0 * verified / total, 1)
    return {
        "dar": dar,
        "total": total,
        "verified": verified,
        "phantoms": phantoms[:12],
        "unresolved": unresolved[:12],
        "note": (
            "DAR = verified imports / imports. Verified means stdlib, a module in this workspace, "
            "or a name declared in a manifest. No registry was contacted."
        ),
    }


def _python_imports(path: Path, relative: str, resolver: _Resolver, local: set[str], declared: set[str]) -> list[dict]:
    tree = resolver.cache.tree(relative)
    if tree is None:
        return []
    found = []
    for node in iter_statements(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append(_classify_module(alias.name, None, relative, node.lineno, resolver, local, declared))
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            if node.level:
                module = _relative_module(path, resolver.profile, node.level, node.module)
            for alias in node.names:
                if alias.name == "*":
                    found.append(_classify_module(module, None, relative, node.lineno, resolver, local, declared))
                else:
                    found.append(_classify_module(module, alias.name, relative, node.lineno, resolver, local, declared))
    return found


def _classify_module(module: str, name: str | None, file: str, line: int, resolver: _Resolver, local: set[str], declared: set[str]) -> dict:
    top = module.split(".")[0]
    record = {"module": module, "name": name, "file": file, "line": line}
    if top in _STDLIB or _norm(top) in declared:
        record["status"] = "verified"
        return record
    if top in local:
        if name and resolver.module_file(f"{module}.{name}") is not None:
            record["status"] = "verified"
            return record
        if resolver.module_file(module) is None or (name and not resolver.symbol_defined(module, name)):
            record["status"] = "unresolved"
            return record
        record["status"] = "verified"
        return record
    record["status"] = "phantom"
    return record


def _module_file(profile: ProjectProfile, module: str) -> str | None:
    parts = module.split(".")
    candidates = []
    if profile.src_layout:
        candidates.append(Path("src", *parts).with_suffix(".py"))
        candidates.append(Path("src", *parts, "__init__.py"))
    candidates.append(Path(*parts).with_suffix(".py"))
    candidates.append(Path(*parts, "__init__.py"))
    root = Path(profile.root)
    for candidate in candidates:
        if (root / candidate).is_file():
            return candidate.as_posix()
    return None


def _relative_module(path: Path, profile: ProjectProfile, level: int, module: str) -> str:
    relative = path.relative_to(profile.root)
    parts = list(relative.parts)
    if profile.src_layout and parts and parts[0] == "src":
        parts = parts[1:]
    package = parts[:-1]
    keep = package[: len(package) - (level - 1)] if level else package
    return ".".join([*keep, module])


def _js_imports(text: str, relative: str, declared: set[str]) -> list[dict]:
    names = re.findall(r"""(?:from|import)\s+["']([^"']+)["']|require\(\s*["']([^"']+)["']\s*\)""", text)
    found = []
    for pair in names:
        spec = next(item for item in pair if item)
        if spec.startswith(".") or spec.startswith("@/"):
            found.append({"module": spec, "name": None, "file": relative, "line": 1, "status": "verified"})
            continue
        top = spec.split("/")[0]
        if top.startswith("@"):
            bits = spec.split("/")
            top = "/".join(bits[:2]) if len(bits) > 1 else top
        status = "verified" if _norm(top) in declared or top in _STDLIB else "phantom"
        found.append({"module": spec, "name": None, "file": relative, "line": 1, "status": status})
    return found


def _local_tops(profile: ProjectProfile) -> set[str]:
    tops = set(profile.packages)
    for relative in [*profile.source_files, *profile.test_files]:
        path = Path(relative)
        parts = list(path.parts)
        if profile.src_layout and parts and parts[0] == "src":
            parts = parts[1:]
        if not parts:
            continue
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = Path(parts[-1]).stem
        if parts and parts[0] not in {"tests", "test", "__tests__"}:
            tops.add(parts[0])
    return tops


def _declared(root: Path) -> set[str]:
    found: set[str] = set()
    for name in ("requirements.txt", "requirements-dev.txt", "requirements.in", "constraints.txt"):
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("-"):
                continue
            token = re.split(r"[<>=!~;\s\[]", stripped, maxsplit=1)[0]
            if token:
                found.add(_norm(token))
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        for line in pyproject.read_text(encoding="utf-8", errors="replace").splitlines():
            if not any(op in line for op in (">=", "==", "~=", "<=", "!=")):
                continue
            for match in re.findall(r"""["']([A-Za-z0-9_.-]+)""", line):
                found.add(_norm(match.split(".")[0]))
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        for key in ("dependencies", "devDependencies", "optionalDependencies"):
            for dep in (data.get(key) or {}):
                found.add(_norm(dep))
    return found


def _firi(profile: ProjectProfile, cache: SourceCache) -> dict:
    tests = 0
    unisolated = []
    for relative in profile.test_files:
        if not relative.endswith(".py"):
            continue
        tree = cache.tree(relative)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            tests += 1
            reason = _unisolated_reason(node)
            if reason:
                unisolated.append({"file": relative, "test": node.name, "line": node.lineno, "reason": reason})
    firi = None if tests == 0 else round(100.0 * len(unisolated) / tests, 1)
    return {
        "firi": firi,
        "tests": tests,
        "unisolated": unisolated[:12],
        "note": (
            "FIRI = tests with direct time, random, filesystem, or network calls, divided by test functions. "
            "This does not re-run the suite."
        ),
    }


def _unisolated_reason(function: ast.AST) -> str | None:
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in {"open", "time.time", "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.date.today"}:
            return name
        if name.endswith(".now") or name.endswith(".utcnow"):
            return name
        if name.startswith("random.") and not name.endswith(".seed"):
            return name
        if name in {"urllib.request.urlopen", "urllib.request.urlretrieve"} or name.endswith("urlopen"):
            return name
        if name.startswith(("socket", "requests", "http.client", "subprocess")) or name.endswith(".system"):
            return name
    return None


def _call_name(node: ast.AST) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _norm(name: str) -> str:
    return name.lower().replace("-", "_")


def attach_measurements(report: dict, *, line_percent: float | None, branch_percent: float | None, measured: bool, mutation: dict) -> dict:
    """Add the dynamic rows. MSI stays out of MRS."""
    msi = mutation.get("msi") if mutation.get("ran") else None
    rows = [
        report["scorecard"][0],
        _row("Statement coverage", line_percent if measured else None, "≥ 80%", _high(line_percent if measured else None, 80, 60)),
        _row("Branch coverage", branch_percent if measured else None, "≥ 75%", _high(branch_percent if measured else None, 75, 50)),
        _row("Mutation score (MSI)", msi, "≥ 70%", _high(msi, 70, 40)),
        *report["scorecard"][1:],
    ]
    report["scorecard"] = rows
    return report


def _scorecard(crap_report: dict, assertions: dict, authenticity: dict, flakiness: dict) -> list[dict]:
    return [
        _row("Dependency authenticity (DAR)", authenticity.get("dar"), "100%", _high(authenticity.get("dar"), 100, 100)),
        _row("Assertion strength (ASR)", assertions.get("asr"), "≥ 85%", _high(assertions.get("asr"), 85, 60)),
        _row("Mean CRAP", crap_report.get("mean"), "≤ 15", _low(crap_report.get("mean"), 15, 30)),
        _row("CRAP > 30", crap_report.get("count_over_30"), "0", _low(crap_report.get("count_over_30"), 0, 0)),
        _row("Flakiness risk (FIRI)", flakiness.get("firi"), "0%", _low(flakiness.get("firi"), 0, 0)),
    ]


def _row(dimension: str, value, threshold: str, status: str) -> dict:
    if isinstance(value, float):
        shown = f"{value:.1f}"
    elif value is None:
        shown = "n/a"
    else:
        shown = str(value)
    return {"dimension": dimension, "value": shown, "threshold": threshold, "status": status}


def _high(value, ok: float, warn: float) -> str:
    if value is None:
        return "n/a"
    if value >= ok:
        return "PASS"
    if value >= warn:
        return "WARN"
    return "FAIL"


def _low(value, ok: float, warn: float) -> str:
    if value is None:
        return "n/a"
    if value <= ok:
        return "PASS"
    if value <= warn:
        return "WARN"
    return "FAIL"
