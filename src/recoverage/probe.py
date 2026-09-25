"""Host side of the out-of-process function probe. One warm worker, killed on timeout."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

from recoverage.models import ProjectProfile
from recoverage.proc import _group_kwargs, _kill_tree, child_env


class ProbeError(RuntimeError):
    pass


class ProbeSession:
    def __init__(self, profile: ProjectProfile, *, call_timeout: float = 2.0):
        self.profile = profile
        self.call_timeout = call_timeout
        self.proc: subprocess.Popen | None = None

    def call(self, file: str, qualname: str, args: tuple, *, trace: bool = False) -> dict:
        return self.request(
            {
                "op": "call",
                "module": _module(file, self.profile.src_layout),
                "qualname": qualname,
                "args": list(args),
                "trace": trace,
            }
        )

    def request(self, message: dict, timeout: float | None = None) -> dict:
        self._ensure()
        assert self.proc is not None and self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        line = self._read(self.call_timeout if timeout is None else timeout)
        if line is None:
            self.close()
            return {"ok": False, "error": "timeout", "value": None, "lines": []}
        if line == "":
            self.close()
            return {"ok": False, "error": "worker-exited", "value": None, "lines": []}
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return {"ok": False, "error": "bad-json", "value": None, "lines": []}
        return payload

    def close(self) -> None:
        process = self.proc
        self.proc = None
        if process is None:
            return
        if process.poll() is None and process.stdin is not None:
            try:
                process.stdin.write(json.dumps({"op": "shutdown"}) + "\n")
                process.stdin.flush()
            except OSError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            process.wait(timeout=5)

    def _ensure(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            return
        env = child_env(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": self.profile.import_root,
            }
        )
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "recoverage.probe_worker"],
            cwd=self.profile.root,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **_group_kwargs(),
        )

    def _read(self, timeout: float) -> str | None:
        assert self.proc is not None and self.proc.stdout is not None
        box: dict[str, str] = {}

        def target() -> None:
            assert self.proc is not None and self.proc.stdout is not None
            box["line"] = self.proc.stdout.readline()

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            return None
        return box.get("line")


def _module(relative: str, src_layout: bool) -> str:
    path = Path(relative)
    if src_layout and path.parts and path.parts[0] == "src":
        path = Path(*path.parts[1:])
    if path.name == "__init__.py":
        parts = path.parts[:-1]
    else:
        parts = path.with_suffix("").parts
    return ".".join(parts)
