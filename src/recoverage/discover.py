"""Find languages, tests, runners, and entry points. No coverage is executed here."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from recoverage.models import ProjectProfile

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "htmlcov",
    ".tox",
    "recoverage-out",
    "sample-report",
    ".next",
    ".turbo",
    "coverage",
    "out",
    "target",
    "vendor",
}
MAX_WALK_FILES = 20_000
MAX_FILE_BYTES = 1_000_000
MAX_WALK_BYTES = 200_000_000
SOURCE_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".php": "php",
    ".cs": "csharp",
}
TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec"}
FLAKE_PATTERNS = (
    re.compile(r"pytest\.mark\.flaky"),
    re.compile(r"@flaky\b"),
    re.compile(r"jest\.retryTimes"),
    re.compile(r"\.retries\s*\("),
)
ENTRY_FILENAMES = {
    "main.py",
    "__main__.py",
    "cli.py",
    "app.py",
    "server.py",
    "index.js",
    "index.ts",
    "main.js",
    "main.ts",
    "server.js",
    "server.ts",
    "app.js",
    "app.ts",
}


def discover(root: Path, budget=None) -> ProjectProfile:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project path is not a directory: {root}")

    from recoverage.host import HostBudget

    budget = budget or HostBudget.detect()
    files, skipped, capped = _walk(
        root,
        walk_files=budget.walk_files,
        walk_bytes=budget.walk_bytes,
        file_bytes=budget.file_bytes,
    )
    src_layout, import_root, packages = _layout(root)
    test_files: list[str] = []
    source_files: list[str] = []
    languages: dict[str, int] = {}
    for path in files:
        relative = path.relative_to(root).as_posix()
        language = SOURCE_EXT.get(path.suffix.lower())
        if language is None:
            continue
        if _is_test(path):
            test_files.append(relative)
            continue
        source_files.append(relative)
        languages[language] = languages.get(language, 0) + 1

    primary = _primary_language(languages, root)
    runner = _test_runner(root, primary, test_files)
    coverage_tool = _coverage_tool(root, primary)
    entry_points = _entry_points(root, source_files)
    flakes = _flake_markers(root, test_files)
    return ProjectProfile(
        root=str(root),
        primary_language=primary,
        languages=sorted(languages),
        test_runner=runner,
        coverage_tool=coverage_tool,
        test_files=sorted(test_files),
        source_files=sorted(source_files),
        entry_points=entry_points,
        packages=packages,
        import_root=str(import_root),
        src_layout=src_layout,
        flake_markers=flakes,
        skipped_projects=skipped,
        notes=_walk_notes(skipped, capped, walk_files=budget.walk_files, walk_bytes=budget.walk_bytes),
    )


_NESTED_MARKERS = ("pyproject.toml", "package.json", "go.mod", "Cargo.toml", "pom.xml")


def _walk(
    root: Path,
    *,
    walk_files: int = MAX_WALK_FILES,
    walk_bytes: int = MAX_WALK_BYTES,
    file_bytes: int = MAX_FILE_BYTES,
) -> tuple[list[Path], list[str], bool]:
    """Walk without entering skip dirs, dot dirs, or nested projects."""
    found: list[Path] = []
    skipped: list[str] = []
    capped = False
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            if name in SKIP_DIRS or name.startswith("."):
                continue
            child = current / name
            if _is_nested_project(child):
                skipped.append(child.relative_to(root).as_posix())
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            # Suffix check first: no stat() syscall for assets, binaries, or lockfiles.
            dot = name.rfind(".")
            if dot < 0 or name[dot:].lower() not in SOURCE_EXT:
                continue
            path = current / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > file_bytes:
                continue
            if path.is_symlink() and not _stays_inside(root, path):
                continue
            found.append(path)
            total_bytes += size
            if len(found) >= walk_files or total_bytes >= walk_bytes:
                capped = True
                break
        if capped:
            break
    return found, skipped, capped


def _is_nested_project(path: Path) -> bool:
    return any((path / name).is_file() for name in _NESTED_MARKERS)


def _walk_notes(
    skipped: list[str],
    capped: bool,
    *,
    walk_files: int = MAX_WALK_FILES,
    walk_bytes: int = MAX_WALK_BYTES,
) -> list[str]:
    notes: list[str] = []
    if skipped:
        shown = ", ".join(skipped[:12])
        extra = f" (+{len(skipped) - 12} more)" if len(skipped) > 12 else ""
        notes.append(
            "Skipped nested projects (own manifest, not part of this run): "
            f"{shown}{extra}. Run recoverage on each directory."
        )
    if capped:
        notes.append(
            f"Discovery stopped at {walk_files} source files or {walk_bytes // 1_000_000} MB. "
            "The report is partial."
        )
    return notes


def _is_test(path: Path) -> bool:
    name = path.name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if ".test." in name or ".spec." in name:
        return True
    return bool(set(path.parts) & TEST_DIR_NAMES)


def _layout(root: Path) -> tuple[bool, Path, list[str]]:
    src = root / "src"
    search = src if src.is_dir() and any(src.glob("*/__init__.py")) else root
    packages: list[str] = []
    for init in sorted(search.glob("*/__init__.py")):
        name = init.parent.name
        if name.startswith(".") or name in TEST_DIR_NAMES or name in SKIP_DIRS:
            continue
        packages.append(name)
    return search == src and src.is_dir(), search, packages


def _stays_inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _primary_language(languages: dict[str, int], root: Path) -> str:
    if not languages:
        return "unknown"
    if (root / "pyproject.toml").is_file() and languages.get("python"):
        return "python"
    if (root / "package.json").is_file() and not (root / "pyproject.toml").is_file():
        javascript = languages.get("javascript", 0)
        typescript = languages.get("typescript", 0)
        scripted = javascript + typescript
        others = max((count for name, count in languages.items() if name not in {"javascript", "typescript"}), default=0)
        if scripted and scripted >= others:
            return "typescript" if typescript >= javascript else "javascript"
    ranked = sorted(languages.items(), key=lambda item: (-item[1], item[0]))
    return ranked[0][0]


def _read_toml(root: Path) -> dict:
    path = root / "pyproject.toml"
    if not path.is_file():
        return {}
    import tomllib

    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_package_json(root: Path) -> dict:
    path = root / "package.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _test_runner(root: Path, primary: str, test_files: list[str]) -> str | None:
    if primary == "python":
        data = _read_toml(root)
        tool = data.get("tool", {})
        if "pytest" in tool or (root / "pytest.ini").is_file() or (root / "conftest.py").is_file():
            return "pytest"
        if (root / "setup.cfg").is_file() and "pytest" in (root / "setup.cfg").read_text(encoding="utf-8"):
            return "pytest"
        if not test_files:
            return None
        sample = "\n".join(
            (root / relative).read_text(encoding="utf-8", errors="replace")[:4000]
            for relative in test_files[:20]
            if (root / relative).is_file()
        )
        if "unittest" in sample and "pytest" not in sample:
            return "unittest"
        return "pytest"
    if primary in {"javascript", "typescript"}:
        package = _read_package_json(root)
        deps = {
            **package.get("dependencies", {}),
            **package.get("devDependencies", {}),
        }
        if (root / "vitest.config.ts").is_file() or (root / "vitest.config.js").is_file() or "vitest" in deps:
            return "vitest"
        if (root / "jest.config.js").is_file() or (root / "jest.config.ts").is_file() or "jest" in deps or "jest" in package:
            return "jest"
        script = package.get("scripts", {}).get("test", "")
        if "vitest" in script:
            return "vitest"
        if "jest" in script:
            return "jest"
        return "jest" if test_files else None
    return None


def _coverage_tool(root: Path, primary: str) -> str | None:
    if primary == "python":
        return "coverage.py"
    if primary not in {"javascript", "typescript"}:
        return None
    package = _read_package_json(root)
    deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    if (root / "node_modules" / ".bin" / "c8").exists() or "c8" in deps:
        return "c8"
    if (root / "node_modules" / ".bin" / "nyc").exists() or "nyc" in deps or "istanbul" in deps:
        return "istanbul"
    return None


def _entry_points(root: Path, source_files: list[str]) -> list[str]:
    found: list[str] = []
    data = _read_toml(root)
    scripts = data.get("project", {}).get("scripts", {})
    if isinstance(scripts, dict):
        for name, target in scripts.items():
            found.append(f"{name}={target}")
    for relative in source_files:
        if Path(relative).name in ENTRY_FILENAMES:
            found.append(relative)
    return found


def _flake_markers(root: Path, test_files: list[str]) -> list[str]:
    hits: list[str] = []
    for relative in test_files:
        path = root / relative
        if relative.endswith(".py"):
            hits.extend(_python_flake_decorators(path, relative))
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FLAKE_PATTERNS:
            if pattern.search(text):
                hits.append(f"{relative}: {pattern.pattern}")
                break
    return hits


def _python_flake_decorators(path: Path, relative: str) -> list[str]:
    import ast

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            text = ast.unparse(decorator)
            if "flaky" in text or "retry" in text:
                hits.append(f"{relative}:{node.lineno} decorator {text}")
                break
    return hits
