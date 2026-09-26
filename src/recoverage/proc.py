"""Child processes: credential allowlist and process-tree kill on timeout."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

# Never copied into a temp working copy. VCS state and dependency trees are the bulk of
# most checkouts and the tests never need them; the child runs recoverage's interpreter.
_COPY_SKIP = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
        "recoverage-out",
    }
)


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _COPY_SKIP or name.endswith(".pyc")}


def temp_copy(root: Path, *, prefix: str) -> tuple[Path, Path]:
    """Copy `root` into a fresh temp dir. Returns (parent_to_rmtree, copied_root).

    Symlinks are copied as links, not followed, so a link that points outside the
    checkout cannot pull foreign files into the copy.
    """
    from recoverage.host import assert_temp_space

    assert_temp_space()
    parent = Path(tempfile.mkdtemp(prefix=prefix))
    copied = parent / "project"
    shutil.copytree(root, copied, symlinks=True, ignore=_copy_ignore)
    return parent, copied

_KEEP = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "PYTHONHASHSEED",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
}


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Minimal environment. Drops API, cloud, CI, SSH, and package-index variables."""
    env = {key: value for key, value in os.environ.items() if key in _KEEP}
    env.update(extra or {})
    env.pop("RECOVERAGE_LLM_API_KEY", None)
    return env


def _group_kwargs() -> dict:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _kill_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()


def run_tree(
    command: list[str],
    *,
    cwd: str,
    env: dict[str, str] | None = None,
    timeout: float = 180,
) -> subprocess.CompletedProcess:
    """Run command. On timeout, kill the process group, not only the direct child."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env if env is not None else child_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **_group_kwargs(),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        process.wait(timeout=10)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
