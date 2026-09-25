"""Search-based input search. On a coverage stall, seed from an LLM or from AST constants."""

from __future__ import annotations

import ast
import importlib
import random
import sys
from pathlib import Path

from recoverage.llm import LLMClient
from recoverage.models import MappedFunction, ProjectProfile
from recoverage.privacy import public_args
from recoverage.probe import ProbeSession

_BANNED = (
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "sqlite3",
    "os.system",
    "eval(",
    "exec(",
    "input(",
    "open(",
    "Popen",
    "parse_args",
    "execute_run",
    "run_analysis",
)


def _load_clean(path: Path) -> tuple[str, ast.AST] | None:
    """Read and parse once per file. None when missing, banned, or unparsable."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if any(token in source for token in _BANNED):
        return None
    try:
        return source, ast.parse(source)
    except SyntaxError:
        return None


def search(
    profile: ProjectProfile,
    functions: list[MappedFunction],
    *,
    client: LLMClient | None,
    generations: int = 6,
    population: int = 10,
    stall_generations: int = 2,
) -> dict:
    """Evolve primitive arguments. Fitness is the count of distinct lines executed inside the function."""
    root = Path(profile.root)
    cases: list[dict] = []
    session = ProbeSession(profile)
    stalls = 0
    agents: list[dict] = []
    targets = [
        function
        for function in functions
        if function.spec.is_public and not function.spec.is_method and function.spec.file.endswith(".py")
    ]
    parsed: dict[str, tuple[str, ast.AST] | None] = {}
    for function in targets:
        relative = function.spec.file
        if relative not in parsed:
            parsed[relative] = _load_clean(root / relative)
        loaded = parsed[relative]
        if loaded is None:
            continue
        source, tree = loaded
        node = _find(tree, function.spec.qualname)
        if not isinstance(node, ast.FunctionDef):
            continue
        segment = ast.get_source_segment(source, node) or ""
        if any(token in segment for token in _BANNED):
            continue
        held = _held_constants(node)
        rng = random.Random(f"{function.spec.qualname}-recoverage")
        people = [_random_args(node, rng) for _ in range(population)]
        covered: set[int] = set()
        best_lines: set[int] = set()
        best_args: tuple | None = None
        best_raised = True
        quiet = 0
        seed_source = "evolutionary"
        stalled_here = False

        def consider(args: tuple, *, source: str | None = None) -> None:
            nonlocal best_lines, best_args, best_raised, seed_source, covered
            _value, error, lines = _trace(session, function.spec.file, function.spec.qualname, args)
            if error is not None and not isinstance(error, (ValueError, TypeError, KeyError)):
                return
            raised = error is not None
            novel = lines - covered
            covered |= lines
            if not lines:
                return
            # Keep a live input. A raising input may add lines to the union without becoming the exported case.
            if raised and not best_raised:
                return
            improved = bool(novel) or (best_raised and not raised) or (not raised and len(lines) > len(best_lines))
            if improved:
                best_lines = set(lines)
                best_args = args
                best_raised = raised
                if source:
                    seed_source = source

        for _generation in range(generations):
            before = set(covered)
            for args in list(people):
                consider(args)
            if covered == before and best_args is not None:
                quiet += 1
            else:
                quiet = 0
            if quiet >= stall_generations and not stalled_here:
                stalled_here = True
                stalls += 1
                seeded, source = _seed(function, node, held, client)
                incoming: list[tuple] = []
                if seeded is not None:
                    incoming.append(seeded)
                for item in _splices(node, held, people):
                    if item not in incoming:
                        incoming.append(item)
                for item in incoming[:24]:
                    consider(item, source=source)
                if incoming:
                    people = [*incoming[:8], *people]
                    agents.append(
                        {
                            "agent": "generator",
                            "action": "sbst-stall-seed",
                            "symbol": function.spec.qualname,
                            "source": source,
                        }
                    )
                quiet = 0
            people = _next_generation(people, node, rng, population)
        if best_args is not None and best_lines:
            cases.append(
                {
                    "module": _module(function.spec.file, profile.src_layout),
                    "qualname": function.spec.qualname,
                    "name": function.spec.name,
                    "file": function.spec.file,
                    "args": public_args(list(best_args)),
                    "lines": sorted(best_lines),
                    "seed_source": seed_source,
                    "spec": _spec(function),
                    "annotation": _return_annotation(node),
                    "raised": best_raised,
                }
            )
    session.close()
    return {"cases": cases, "stalls": stalls, "agents": agents, "llm": client is not None}


def _seed(function: MappedFunction, node: ast.FunctionDef, held: dict[str, list], client: LLMClient | None):
    if client is not None:
        try:
            raw = client.complete(
                system="Return a JSON array of positional arguments that reach the unexecuted branch. JSON only.",
                user=f"function {function.spec.qualname} parameters {function.spec.parameters}",
            )
        except Exception:
            raw = ""
        parsed = _parse_args(raw)
        if parsed is not None:
            return tuple(parsed), "llm"
    names = [arg.arg for arg in node.args.args if arg.arg not in {"self", "cls"}]
    if not names:
        return tuple(), "ast-constants"
    values = []
    for name in names:
        choices = held.get(name) or []
        values.append(choices[0] if choices else None)
    return tuple(values), "ast-constants"


def _splices(node: ast.FunctionDef, held: dict[str, list], people: list[tuple]) -> list[tuple]:
    """Drop each AST constant into an existing individual so a guard value is not stuck on the first parameter."""
    names = [arg.arg for arg in node.args.args if arg.arg not in {"self", "cls"}]
    seeded: list[tuple] = []
    for person in people[:8]:
        values = list(person)
        if len(values) < len(names):
            continue
        for index, name in enumerate(names):
            for constant in (held.get(name) or [])[:4]:
                mutant = list(values)
                mutant[index] = constant
                seeded.append(tuple(mutant))
    return seeded


def _parse_args(raw: str) -> list | None:
    import json

    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1]
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if isinstance(value, list) and all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
        return value
    return None


def _trace(session: ProbeSession, file: str, qualname: str, args: tuple):
    payload = session.call(file, qualname, args, trace=True)
    kind = payload.get("error")
    if not kind:
        return payload.get("value"), None, set(payload.get("lines") or [])
    mapped = {"ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError}.get(kind, RuntimeError)
    return None, mapped(kind), set(payload.get("lines") or [])


def _load_module(profile: ProjectProfile, relative: str, module: str):
    """Import `module`, unless sys.modules already holds a different file under that name."""
    imported = importlib.import_module(module)
    expected = (Path(profile.root) / relative).resolve()
    actual_file = getattr(imported, "__file__", None)
    actual = Path(actual_file).resolve() if actual_file else None
    if actual != expected:
        sys.modules.pop(module, None)
        imported = importlib.import_module(module)
    return imported


def _random_args(node: ast.FunctionDef, rng: random.Random) -> tuple:
    values = []
    for arg in node.args.args:
        if arg.arg in {"self", "cls"}:
            continue
        annotation = ast.unparse(arg.annotation) if arg.annotation is not None else ""
        values.append(_draw(arg.arg, annotation, rng))
    return tuple(values)


def _draw(name: str, annotation: str, rng: random.Random):
    lowered = annotation.lower()
    if "bool" in lowered or name in {"authorized", "enabled", "flag"}:
        return rng.choice([True, False])
    if "list" in lowered:
        return rng.choice([[], [1.0, 2.0], [1.0], [-1.0]])
    if "float" in lowered or name in {"amount", "subtotal", "subtotal_amount", "price", "captured"}:
        return rng.choice([-1.0, 0.0, 1.0, 2.5, 10.0, 49.0, 100.0])
    if "int" in lowered or name in {"units", "qty"}:
        return rng.choice([-1, 0, 1, 10, 11, 100, 101])
    if "str" in lowered or name in {"method", "coupon", "tier", "token", "code"}:
        return rng.choice(["", "x", "a", "b"])
    return rng.choice([None, 0, 1, "x", True])


def _next_generation(people: list[tuple], node: ast.FunctionDef, rng: random.Random, size: int) -> list[tuple]:
    if not people:
        return [_random_args(node, rng) for _ in range(size)]
    nxt = list(people[: max(1, size // 3)])
    while len(nxt) < size:
        parent = list(rng.choice(people))
        if parent:
            index = rng.randrange(len(parent))
            parent[index] = _mutate(parent[index], rng)
        nxt.append(tuple(parent))
    return nxt


def _mutate(value, rng: random.Random):
    if isinstance(value, bool):
        return not value
    if isinstance(value, float):
        return rng.choice([value + 1, value - 1, value * 2, 0.0, -1.0, 100.0])
    if isinstance(value, int) and not isinstance(value, bool):
        return rng.choice([value + 1, value - 1, 0, 1, 100, -1])
    if isinstance(value, str):
        return rng.choice(["", "x", "a", value + "z", "other"])
    if isinstance(value, list):
        return rng.choice([[], [1.0], [-1.0], value + [1.0]])
    return value


def _held_constants(node: ast.FunctionDef) -> dict[str, list]:
    names = [arg.arg for arg in node.args.args if arg.arg not in {"self", "cls"}]
    found = {name: [] for name in names}

    def add(name: str, value) -> None:
        if name in found and value not in found[name] and isinstance(value, (str, int, float)) and not isinstance(value, bool):
            found[name].append(value)

    for child in ast.walk(node):
        if isinstance(child, ast.Compare) and isinstance(child.left, ast.Name):
            for comp in child.comparators:
                if isinstance(comp, ast.Constant):
                    add(child.left.id, comp.value)
                elif isinstance(comp, (ast.Set, ast.Tuple, ast.List)):
                    for elt in comp.elts:
                        if isinstance(elt, ast.Constant):
                            add(child.left.id, elt.value)
    return found


def _spec(function: MappedFunction) -> str:
    params = ", ".join(function.spec.parameters) or "no parameters"
    return (
        f"{function.spec.qualname}({params}) is specified from its signature and name only. "
        "The expected behavior is a deterministic structured result for valid inputs. "
        "This spec deliberately ignores observed return values so a buggy implementation is not frozen into the test."
    )


def _return_annotation(node: ast.FunctionDef) -> str:
    if node.returns is None:
        return ""
    return ast.unparse(node.returns)


def _module(relative: str, src_layout: bool) -> str:
    path = Path(relative)
    if src_layout and path.parts and path.parts[0] == "src":
        path = Path(*path.parts[1:])
    if path.name == "__init__.py":
        parts = path.parts[:-1]
    else:
        parts = path.with_suffix("").parts
    return ".".join(parts)


def _find(tree: ast.AST, qualname: str):
    if not isinstance(tree, ast.Module):
        return None
    class_name, _, func_name = qualname.partition(".")
    if not func_name:
        func_name = class_name
        class_name = ""
    if class_name:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return node
    return None
