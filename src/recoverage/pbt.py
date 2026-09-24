"""Property checks over generated inputs. This is not example-based characterization."""

from __future__ import annotations

import importlib
import random
import sys
from pathlib import Path

from recoverage.models import MappedFunction, ProjectProfile

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
    "parse_args",
    "execute_run",
    "run_analysis",
)


def run_properties(profile: ProjectProfile, functions: list[MappedFunction], *, trials: int = 1000) -> dict:
    targets = _targets(profile, functions)
    if not targets:
        return {
            "ran": False,
            "trials": 0,
            "passed": 0,
            "failed": 0,
            "falsified": [],
            "properties": [],
            "note": "No pure public functions were safe to fuzz.",
        }
    per = max(1, trials // len(targets))
    # The PRD floor is 1,000 synthetic inputs for the run, not a slogan.
    if per * len(targets) < trials:
        per = trials
    passed = 0
    failed = 0
    falsified: list[dict] = []
    properties: list[dict] = []
    root_inserted = profile.import_root not in sys.path
    if root_inserted:
        sys.path.insert(0, profile.import_root)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        for function in targets:
            module = _module(function.spec.file, profile.src_layout)
            imported = _load_module(profile, function.spec.file, module)
            target = getattr(imported, function.spec.name)
            rng = random.Random(function.spec.qualname)
            local_pass = 0
            local_fail = 0
            kinds = ("structural", "determinism", "entity-substitution")
            for index in range(per):
                kind = kinds[index % 3]
                args = _sample(function, rng, kind)
                ok, shrunk = _check(target, args, kind, function)
                if ok:
                    passed += 1
                    local_pass += 1
                else:
                    failed += 1
                    local_fail += 1
                    if len(falsified) < 8:
                        falsified.append(
                            {
                                "symbol": function.spec.qualname,
                                "property": kind,
                                "args": _jsonable(shrunk),
                            }
                        )
            properties.append(
                {
                    "symbol": function.spec.qualname,
                    "module": module,
                    "file": function.spec.file,
                    "parameters": function.spec.parameters,
                    "trials": per,
                    "passed": local_pass,
                    "failed": local_fail,
                    "kinds": list(kinds),
                }
            )
    finally:
        sys.dont_write_bytecode = previous
        if root_inserted and profile.import_root in sys.path:
            sys.path.remove(profile.import_root)
    total = passed + failed
    return {
        "ran": True,
        "trials": total,
        "passed": passed,
        "failed": failed,
        "falsified": falsified,
        "properties": properties,
        "note": (
            f"Ran {total} property trials across structural conformance, determinism, "
            "and entity substitution. Failing inputs were shrunk toward simpler values."
        ),
    }


def _targets(profile: ProjectProfile, functions: list[MappedFunction]) -> list[MappedFunction]:
    root = Path(profile.root)
    chosen = []
    for function in functions:
        if not function.spec.is_public or function.spec.is_method or not function.spec.file.endswith(".py"):
            continue
        path = root / function.spec.file
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(token in text for token in _BANNED):
            continue
        chosen.append(function)
    return chosen[:4]


def _check(target, args: tuple, kind: str, function: MappedFunction) -> tuple[bool, tuple]:
    try:
        first = target(*args)
        second = target(*args) if kind == "determinism" else first
    except (TypeError, ValueError, KeyError, OverflowError):
        return True, args
    except Exception:
        return False, _shrink(target, args, kind, function)
    if kind == "determinism" and first != second:
        return False, _shrink(target, args, kind, function)
    if kind == "structural" and not _shape_ok(first, function):
        return False, _shrink(target, args, kind, function)
    if kind == "entity-substitution":
        swapped = _swap_strings(args)
        try:
            other = target(*swapped)
        except (TypeError, ValueError, KeyError, OverflowError):
            return True, args
        except Exception:
            return False, _shrink(target, swapped, kind, function)
        if type(other) is not type(first):
            return False, _shrink(target, args, kind, function)
    return True, args


def _shape_ok(value, function: MappedFunction) -> bool:
    if value is None:
        return True
    return isinstance(value, (int, float, str, bool, dict, list, tuple))


def _shrink(target, args: tuple, kind: str, function: MappedFunction) -> tuple:
    current = args
    for _ in range(6):
        nxt = tuple(_simpler(value) for value in current)
        if nxt == current:
            break
        ok, _ = _check_once(target, nxt, kind)
        current = nxt
        if ok:
            break
    return current


def _check_once(target, args: tuple, kind: str) -> tuple[bool, tuple]:
    try:
        first = target(*args)
        if kind == "determinism":
            second = target(*args)
            return first == second, args
        return True, args
    except (TypeError, ValueError, KeyError, OverflowError):
        return True, args
    except Exception:
        return False, args


def _simpler(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, float):
        return 0.0 if abs(value) < 1 else value / 2
    if isinstance(value, int) and not isinstance(value, bool):
        return 0 if abs(value) <= 1 else value // 2
    if isinstance(value, str):
        return value[:-1]
    if isinstance(value, list):
        return value[:-1]
    return value


def _sample(function: MappedFunction, rng: random.Random, kind: str) -> tuple:
    values = []
    for name in function.spec.parameters:
        if kind == "entity-substitution" and _looks_like_string(name):
            values.append(rng.choice(["alice", "bob", "sku-1", "sku-2", "north", "south"]))
        elif name in {"amount", "subtotal", "subtotal_amount", "price", "captured"}:
            values.append(rng.choice([-1.0, 0.0, 1.0, 10.0, 50.0, 100.0, 999.99, 1000.0]))
        elif name in {"units", "qty"}:
            values.append(rng.choice([-1, 0, 1, 10, 11, 100, 101]))
        elif name in {"authorized", "enabled", "flag"}:
            values.append(rng.choice([True, False]))
        elif name in {"method", "coupon", "tier", "token", "code"}:
            values.append(rng.choice(["", "x", "card", "ach", "pro", "free", "SAVE10"]))
        elif name in {"prices"}:
            values.append(rng.choice([[], [1.0, 2.0], [-1.0], [999.99]]))
        else:
            values.append(rng.choice([0, 1, "x", None, True]))
    return tuple(values)


def _looks_like_string(name: str) -> bool:
    return name in {"method", "coupon", "tier", "token", "code", "name", "sku"}


def _swap_strings(args: tuple) -> tuple:
    swapped = []
    for value in args:
        if isinstance(value, str):
            swapped.append({"alice": "bob", "bob": "alice"}.get(value, value + "-b"))
        else:
            swapped.append(value)
    return tuple(swapped)


def _jsonable(args: tuple):
    out = []
    for value in args:
        if isinstance(value, (str, int, float, bool)) or value is None:
            out.append(value)
        else:
            out.append(repr(value))
    return out


def _load_module(profile: ProjectProfile, relative: str, module: str):
    imported = importlib.import_module(module)
    expected = (Path(profile.root) / relative).resolve()
    actual_file = getattr(imported, "__file__", None)
    actual = Path(actual_file).resolve() if actual_file else None
    if actual != expected:
        sys.modules.pop(module, None)
        imported = importlib.import_module(module)
    return imported


def _module(relative: str, src_layout: bool) -> str:
    path = Path(relative)
    if src_layout and path.parts and path.parts[0] == "src":
        path = Path(*path.parts[1:])
    parts = path.with_suffix("").parts
    return ".".join(parts)
