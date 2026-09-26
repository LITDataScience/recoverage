"""Map source files to functions, branches, and risk tags."""

from __future__ import annotations

import ast
import bisect
import re
from pathlib import Path

from recoverage.models import RISK_THRESHOLD, FileStructure, FunctionSpec, ProjectProfile
from recoverage.sources import SourceCache

_NAME_RISK: tuple[tuple[str, float, str], ...] = (
    ("password", 0.95, "auth"),
    ("passwd", 0.9, "auth"),
    ("secret", 0.85, "secret"),
    ("auth", 0.8, "auth"),
    ("login", 0.7, "auth"),
    ("token", 0.75, "auth"),
    ("session", 0.55, "auth"),
    ("charge", 0.9, "payment"),
    ("refund", 0.85, "payment"),
    ("payment", 0.9, "payment"),
    ("billing", 0.75, "payment"),
    ("invoice", 0.55, "payment"),
    ("coupon", 0.45, "payment"),
    ("encrypt", 0.85, "crypto"),
    ("decrypt", 0.85, "crypto"),
    ("permission", 0.7, "authz"),
    ("admin", 0.6, "authz"),
    ("sudo", 0.85, "authz"),
    ("purge", 0.6, "destructive"),
    ("delete", 0.4, "destructive"),
)
_BODY_RISK: tuple[tuple[re.Pattern[str], float, str], ...] = (
    (re.compile(r"\beval\s*\("), 0.9, "eval"),
    (re.compile(r"\bexec\s*\("), 0.85, "exec"),
    (re.compile(r"\bsubprocess\b"), 0.7, "subprocess"),
    (re.compile(r"\bpickle\b"), 0.55, "pickle"),
    (re.compile(r"\bos\.system\b"), 0.75, "shell"),
    (re.compile(r"shell\s*=\s*True"), 0.8, "shell"),
    (re.compile(r"\bcursor\.execute\b"), 0.55, "sql"),
    (re.compile(r"\bpassword\b"), 0.35, "auth"),
    (re.compile(r"\bsecret\b"), 0.35, "secret"),
)
_JS_FUNC = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"
    r"|^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
    r"|^\s*(?:public|private|protected|static|async|export|\s)*([A-Za-z_$][\w$]*)\s*\([^;]*\)\s*\{",
    re.M,
)
_JS_KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "function",
    "return",
    "else",
    "do",
    "try",
    "with",
}
_GENERIC_FUNC = re.compile(
    r"^\s*(?:func|fn|def|function)\s+(?:\([^)]*\)\s*)?([A-Za-z_][\w]*)"
    r"|^\s*(?:public|private|protected)?\s*(?:static\s+)?[\w.<>,\[\]]+\s+([A-Za-z_][\w]*)\s*\(",
    re.M,
)


def analyze_project(
    profile: ProjectProfile,
    cache: SourceCache | None = None,
    *,
    workers: int = 1,
) -> list[FileStructure]:
    root = Path(profile.root)
    cache = cache or SourceCache(root)
    jobs: list[tuple[str, str, str]] = []
    for relative in profile.source_files:
        text = cache.text(relative)
        if text is None:
            continue
        jobs.append((relative, _language_for(root / relative), text))
    if workers <= 1 or len(jobs) <= 1:
        return [_analyze_file(relative, language, text, profile.src_layout, cache) for relative, language, text in jobs]
    from concurrent.futures import ThreadPoolExecutor

    def _one(job: tuple[str, str, str]) -> FileStructure:
        relative, language, text = job
        # Parse from the text. The cache is not safe to mutate from these threads.
        return _analyze_file(relative, language, text, profile.src_layout, None)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, jobs))


def _language_for(path: Path) -> str:
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
    }.get(path.suffix.lower(), path.suffix.lower().lstrip(".") or "generic")


def _analyze_file(relative: str, language: str, text: str, src_layout: bool, cache: SourceCache | None = None) -> FileStructure:
    module = _module_name(relative, src_layout)
    package = module.split(".")[0] if "." in module else module
    if language == "python":
        return _analyze_python(relative, text, module, package, cache)
    if language in {"javascript", "typescript"}:
        return _analyze_js(relative, language, text, module, package)
    return _analyze_generic(relative, language, text, module, package)


def _module_name(relative: str, src_layout: bool) -> str:
    path = Path(relative)
    if src_layout and path.parts and path.parts[0] == "src":
        path = Path(*path.parts[1:])
    if path.name == "__init__.py":
        parts = path.parts[:-1]
    else:
        parts = path.with_suffix("").parts
    return ".".join(parts) if parts else path.stem


def _analyze_python(relative: str, text: str, module: str, package: str, cache: SourceCache | None = None) -> FileStructure:
    try:
        tree = cache.tree(relative) if cache is not None else ast.parse(text)
        if tree is None:
            # The cache swallows the SyntaxError; re-parse here only to get the message.
            ast.parse(text)
            raise SyntaxError("unparsable")
    except SyntaxError as exc:
        return FileStructure(
            path=relative,
            language="python",
            package=package,
            module=module,
            line_count=text.count("\n") + 1,
            statement_count=0,
            functions=[],
            parse_error=f"SyntaxError: {exc.msg} (line {exc.lineno})",
        )
    functions = _python_functions(tree, relative, module)
    return FileStructure(
        path=relative,
        language="python",
        package=package,
        module=module,
        line_count=text.count("\n") + 1,
        statement_count=len(_statement_lines(tree)),
        functions=functions,
        parse_error=None,
    )


def _statement_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in iter_statements(tree):
        lineno = getattr(node, "lineno", None)
        if lineno:
            lines.add(lineno)
    if isinstance(tree, ast.Module) and tree.body and isinstance(tree.body[0], ast.Expr):
        value = tree.body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            lines.discard(tree.body[0].lineno)
    return lines


# Nodes whose children can contain statements. Expressions never do (a lambda is not a
# FunctionDef), so skipping them cuts the statement walk to the statement skeleton.
_BLOCK_NODES = (ast.stmt, ast.ExceptHandler, ast.match_case, ast.Module, ast.Interactive)


def iter_statements(tree: ast.AST):
    """Every ast.stmt in the tree, visiting only statement-bearing nodes: O(statements)."""
    stack = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.stmt):
            yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _BLOCK_NODES):
                stack.append(child)


def _python_functions(tree: ast.AST, relative: str, module: str) -> list[FunctionSpec]:
    """Iterative statement-skeleton walk. Nested defs are found; expressions are never entered."""
    found: list[FunctionSpec] = []
    stack: list[tuple[ast.AST, str | None]] = [(tree, None)]
    while stack:
        node, class_name = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not tree:
            found.append(_function_spec(node, relative, module, class_name))
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, _BLOCK_NODES):
                continue
            # A class sets the name its methods inherit. Functions pass their enclosing class down unchanged.
            stack.append((child, child.name if isinstance(child, ast.ClassDef) else class_name))
    found.sort(key=lambda item: (item.lineno, item.qualname))
    return found


def _function_spec(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative: str,
    module: str,
    class_name: str | None,
) -> FunctionSpec:
    name = node.name
    qualname = f"{class_name}.{name}" if class_name else name
    params = [arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]]
    params = [param for param in params if param not in {"self", "cls"}]
    branches, statement_lines = _body_metrics(node)
    complexity = 1 + branches
    risk_score, tags = _risk(name, "", complexity)
    return FunctionSpec(
        name=name,
        qualname=qualname,
        file=relative,
        lineno=node.lineno,
        end_lineno=node.end_lineno or node.lineno,
        branch_count=branches,
        complexity=complexity,
        is_public=not name.startswith("_"),
        risk_score=risk_score,
        risk_tags=tags,
        parameters=params,
        is_method=class_name is not None,
        statement_lines=statement_lines,
    )


_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_DECISION_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler, ast.Match, ast.Assert)


def _body_metrics(node: ast.AST) -> tuple[int, list[int]]:
    """Decision points and statement lines of one function body in a single iterative pass.

    Nested defs and classes are their own scope and are not descended. This used to be
    two recursive walks per function; on a 20_000-function tree that was 2M extra visits.
    """
    decisions = 0
    lines: set[int] = set()
    if getattr(node, "lineno", None):
        lines.add(node.lineno)
    stack = [node]
    while stack:
        current = stack.pop()
        for child in ast.iter_child_nodes(current):
            if isinstance(child, _SCOPE_NODES):
                continue
            if isinstance(child, ast.stmt):
                lineno = getattr(child, "lineno", None)
                if lineno:
                    lines.add(lineno)
                if isinstance(child, _DECISION_NODES):
                    decisions += 1
            elif isinstance(child, _DECISION_NODES):
                decisions += 1
            elif isinstance(child, ast.BoolOp):
                decisions += max(0, len(child.values) - 1)
            elif isinstance(child, ast.comprehension):
                decisions += len(child.ifs)
            stack.append(child)
    return decisions, sorted(lines)


def _complexity(node: ast.AST) -> tuple[int, int]:
    decisions, _lines = _body_metrics(node)
    return decisions, 1 + decisions


def _risk(name: str, source: str, complexity: int) -> tuple[float, list[str]]:
    lowered = name.lower()
    score = 0.0
    tags: list[str] = []
    for needle, weight, tag in _NAME_RISK:
        if needle in lowered:
            score = max(score, weight)
            if tag not in tags:
                tags.append(tag)
    for pattern, weight, tag in _BODY_RISK:
        if pattern.search(source):
            score = min(1.0, score + weight * 0.5)
            if tag not in tags:
                tags.append(tag)
    if complexity >= 8:
        score = min(1.0, score + 0.15)
        if "complexity" not in tags:
            tags.append("complexity")
    return round(score, 3), tags


def attach_sources(structures: list[FileStructure], root: Path, cache: SourceCache | None = None) -> None:
    """Recompute risk using real function source. The first pass has empty bodies."""
    cache = cache or SourceCache(root)
    for structure in structures:
        if structure.language != "python" or structure.parse_error:
            continue
        text = cache.text(structure.path)
        if text is None:
            continue
        lines = text.splitlines()
        for function in structure.functions:
            body = "\n".join(lines[function.lineno - 1 : function.end_lineno])
            score, tags = _risk(function.name, body, function.complexity)
            function.risk_score = score
            function.risk_tags = tags


def _line_locator(text: str):
    """O(1) amortised offset→line. Newline offsets are collected once; lookups bisect."""
    starts = [index + 1 for index, char in enumerate(text) if char == "\n"]

    def line_of(offset: int) -> int:
        return bisect.bisect_right(starts, offset) + 1

    return line_of


def _analyze_js(relative: str, language: str, text: str, module: str, package: str) -> FileStructure:
    functions: list[FunctionSpec] = []
    lines = text.splitlines()
    line_of = _line_locator(text)
    for match in _JS_FUNC.finditer(text):
        name = next(group for group in match.groups() if group)
        if name in _JS_KEYWORDS:
            continue
        start = line_of(match.start())
        end = _brace_end(lines, start - 1)
        body = "\n".join(lines[start - 1 : end])
        branches = len(re.findall(r"\b(if|else if|for|while|case|catch)\b|\?(?!=)", body))
        score, tags = _risk(name, body, 1 + branches)
        functions.append(
            FunctionSpec(
                name=name,
                qualname=name,
                file=relative,
                lineno=start,
                end_lineno=end,
                branch_count=branches,
                complexity=1 + branches,
                is_public=not name.startswith("_"),
                risk_score=score,
                risk_tags=tags,
                parameters=_js_params(match.group(0)),
                is_method=False,
                statement_lines=list(range(start, end + 1)),
            )
        )
    return FileStructure(
        path=relative,
        language=language,
        package=package,
        module=module,
        line_count=len(lines) or 1,
        statement_count=max(len(functions), text.count("\n") // 2),
        functions=functions,
        parse_error=None,
    )


def _brace_end(lines: list[str], start_index: int) -> int:
    depth = 0
    seen = False
    for index in range(start_index, len(lines)):
        depth += lines[index].count("{")
        depth -= lines[index].count("}")
        if "{" in lines[index]:
            seen = True
        if seen and depth <= 0:
            return index + 1
    return len(lines)


def _js_params(signature: str) -> list[str]:
    match = re.search(r"\(([^)]*)\)", signature)
    if not match or not match.group(1).strip():
        return []
    params = []
    for raw in match.group(1).split(","):
        name = raw.strip().split("=")[0].strip().lstrip("{").rstrip("}")
        name = re.sub(r"[^A-Za-z0-9_$].*", "", name)
        if name:
            params.append(name)
    return params


def _analyze_generic(relative: str, language: str, text: str, module: str, package: str) -> FileStructure:
    functions: list[FunctionSpec] = []
    line_of = _line_locator(text)
    for match in _GENERIC_FUNC.finditer(text):
        name = next(group for group in match.groups() if group)
        if name in _JS_KEYWORDS:
            continue
        lineno = line_of(match.start())
        score, tags = _risk(name, "", 1)
        functions.append(
            FunctionSpec(
                name=name,
                qualname=name,
                file=relative,
                lineno=lineno,
                end_lineno=lineno,
                branch_count=0,
                complexity=1,
                is_public=not name.startswith("_"),
                risk_score=score,
                risk_tags=tags,
                parameters=[],
                is_method=False,
                statement_lines=[lineno],
            )
        )
    return FileStructure(
        path=relative,
        language=language,
        package=package,
        module=module,
        line_count=text.count("\n") + 1,
        statement_count=max(1, len(functions)),
        functions=functions,
        parse_error=None,
    )


def high_risk(function: FunctionSpec) -> bool:
    return function.risk_score >= RISK_THRESHOLD
