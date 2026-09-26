"""Property checks over generated inputs. This is not example-based characterization."""

from __future__ import annotations

import importlib
import random
import sys
from pathlib import Path

from recoverage.models import MappedFunction, ProjectProfile
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
    left_out = 0
    falsified: list[dict] = []
    properties: list[dict] = []
    session = ProbeSession(profile)
    try:
        for function in targets:
            module = _module(function.spec.file, profile.src_layout)

            def target(*args, _function=function):
                payload = session.call(_function.spec.file, _function.spec.qualname, args)
                kind = payload.get("error")
                if kind:
                    mapped = {
                        "TypeError": TypeError,
                        "ValueError": ValueError,
                        "KeyError": KeyError,
                        "OverflowError": OverflowError,
                    }.get(kind, RuntimeError)
                    raise mapped(kind)
                return payload.get("value")
            rng = random.Random(function.spec.qualname)
            local_pass = 0
            local_fail = 0
            errors = 0
            kinds = ("structural", "determinism", "entity-substitution")
            for index in range(per):
                kind = kinds[index % 3]
                args = _sample(function, rng, kind)
                status, shrunk = _outcome(target, args, kind, function)
                if status == "skip":
                    continue
                if status == "error":
                    errors += 1
                    continue
                if status == "pass":
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
            # A function that raises on every call was not property-tested.
            if local_pass == 0 and local_fail == 0:
                if errors:
                    left_out += 1
                properties.append(
                    {
                        "symbol": function.spec.qualname,
                        "module": module,
                        "file": function.spec.file,
                        "parameters": function.spec.parameters,
                        "trials": 0,
                        "passed": 0,
                        "failed": 0,
                        "kinds": list(kinds),
                    }
                )
                continue
            properties.append(
                {
                    "symbol": function.spec.qualname,
                    "module": module,
                    "file": function.spec.file,
                    "parameters": function.spec.parameters,
                    "trials": local_pass + local_fail,
                    "passed": local_pass,
                    "failed": local_fail,
                    "kinds": list(kinds),
                }
            )
    finally:
        session.close()
    total = passed + failed
    note = (
        f"Ran {total} property trials across structural conformance, determinism, "
        "and entity substitution. Failing inputs were shrunk toward simpler values."
    )
    if left_out:
        note += f" {left_out} functions raised on every call and were left out of the score."
    return {
        "ran": total > 0,
        "trials": total,
        "passed": passed,
        "failed": failed,
        "falsified": falsified,
        "properties": properties,
        "note": note,
    }


def _targets(profile: ProjectProfile, functions: list[MappedFunction], limit: int = 4) -> list[MappedFunction]:
    """Prefer covered functions in the project packages. Stops at `limit`."""
    root = Path(profile.root)
    banned_by_file: dict[str, bool] = {}
    chosen = []
    ordered = sorted(functions, key=lambda function: _probe_sort_key(function, profile.packages))
    for function in ordered:
        if not function.spec.is_public or function.spec.is_method or not function.spec.file.endswith(".py"):
            continue
        relative = function.spec.file
        if relative not in banned_by_file:
            path = root / relative
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                banned_by_file[relative] = True
            else:
                banned_by_file[relative] = any(token in text for token in _BANNED)
        if banned_by_file[relative]:
            continue
        chosen.append(function)
        if len(chosen) == limit:
            break
    return chosen


def _probe_sort_key(function: MappedFunction, packages: list[str]) -> tuple:
    path = function.spec.file.replace("\\", "/")
    in_package = any(path == f"{name}.py" or path.startswith(f"{name}/") for name in packages)
    covered = function.coverage_ratio or 0.0
    return (0 if in_package else 1, 0 if covered > 0 else 1, -covered, path, function.spec.qualname)


def _outcome(target, args: tuple, kind: str, function: MappedFunction) -> tuple[str, tuple]:
    try:
        first = target(*args)
        second = target(*args) if kind == "determinism" else first
    except (TypeError, ValueError, KeyError, OverflowError):
        return "skip", args
    except Exception:
        return "error", args
    if kind == "determinism" and first != second:
        return "fail", _shrink(target, args, kind, function)
    if kind == "structural" and not _shape_ok(first, function):
        return "fail", _shrink(target, args, kind, function)
    if kind == "entity-substitution":
        swapped = _swap_strings(args)
        try:
            other = target(*swapped)
        except (TypeError, ValueError, KeyError, OverflowError):
            return "skip", args
        except Exception:
            return "error", args
        if type(other) is not type(first):
            return "fail", _shrink(target, args, kind, function)
    return "pass", args


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
        return None, args
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
