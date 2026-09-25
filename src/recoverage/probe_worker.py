"""Isolated interpreter for one project's function calls. Stdin JSON, stdout JSON."""

from __future__ import annotations

import importlib
import json
import sys
import time
import traceback


def main() -> int:
    sys.dont_write_bytecode = True
    loaded: dict[str, object] = {}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            _emit({"ok": False, "error": "bad-json", "lines": []})
            continue
        if message.get("op") == "shutdown":
            return 0
        try:
            if message.get("op") == "time":
                _emit(_time(message, loaded))
            else:
                _emit(_call(message, loaded))
        except Exception as exc:
            _emit({"ok": False, "error": type(exc).__name__, "detail": traceback.format_exc()[-500:], "lines": []})
    return 0


def _call(message: dict, loaded: dict) -> dict:
    module_name = str(message.get("module") or "")
    qualname = str(message.get("qualname") or "")
    name = qualname.split(".")[-1]
    args = message.get("args") or []
    if not isinstance(args, list):
        return {"ok": False, "error": "bad-args", "lines": []}
    key = module_name
    if key not in loaded:
        loaded[key] = importlib.import_module(module_name)
    target = getattr(loaded[key], name)
    lines: list[int] = []
    trace = bool(message.get("trace"))
    previous = sys.gettrace()

    def tracer(frame, event, arg):
        if event == "line" and frame.f_code.co_name == name:
            lines.append(frame.f_lineno)
        return tracer

    if trace:
        sys.settrace(tracer)
    try:
        value = target(*args)
        error = None
    except Exception as exc:
        value = None
        error = type(exc).__name__
    finally:
        if trace:
            sys.settrace(previous)
    return {"ok": error is None, "error": error, "value": _jsonable(value), "lines": lines}


def _time(message: dict, loaded: dict) -> dict:
    repeats = message.get("repeats") or 1
    if not isinstance(repeats, int) or repeats < 1 or repeats > 50:
        return {"ok": False, "error": "bad-repeats", "samples": []}
    module_name = str(message.get("module") or "")
    qualname = str(message.get("qualname") or "")
    name = qualname.split(".")[-1]
    args = message.get("args") or []
    if not isinstance(args, list):
        return {"ok": False, "error": "bad-args", "samples": []}
    if module_name not in loaded:
        loaded[module_name] = importlib.import_module(module_name)
    target = getattr(loaded[module_name], name)
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        try:
            target(*args)
        except Exception as exc:
            return {"ok": False, "error": type(exc).__name__, "samples": []}
        samples.append(time.perf_counter() - start)
    return {"ok": True, "error": None, "samples": samples, "lines": []}


def _jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return type(value).__name__


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
