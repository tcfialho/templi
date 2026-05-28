"""Lock de escrita do manifesto durante hooks (applies aninhados via subprocess)."""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from templi.core.runtime_config import get_manifest_dir
from templi.utils.file_utils import ensure_directory

_LOCK_FILE_NAME = "manifest.lock"
_STALE_LOCK_SECONDS = 4 * 60 * 60


def manifest_lock_path(project_dir: str) -> Path:
    manifest_dir = Path(project_dir) / get_manifest_dir()
    return manifest_dir / _LOCK_FILE_NAME


def is_manifest_write_locked(project_dir: str) -> bool:
    path = manifest_lock_path(project_dir)
    if not path.is_file():
        return False
    if _is_stale_lock(path):
        path.unlink(missing_ok=True)
        return False
    return True


@contextmanager
def manifest_write_lock(project_dir: str) -> Iterator[None]:
    """Apply raiz segura o lock; applies aninhados detectam e nao escrevem.

    Quando outro apply vivo ja segura o lock (apply aninhado via subprocess do
    hook run), este apply roda como no-op: nao sobrescreve o lock nem o remove
    ao sair, e update_manifest pula a escrita via is_manifest_write_locked.
    """
    path = manifest_lock_path(project_dir)
    ensure_directory(path.parent)
    acquired = _try_acquire_lock_file(path)
    try:
        yield
    finally:
        if acquired:
            path.unlink(missing_ok=True)


def _try_acquire_lock_file(path: Path) -> bool:
    if path.is_file() and not _is_stale_lock(path):
        return False
    path.write_text(_lock_payload(), encoding="utf-8")
    return True


def _lock_payload() -> str:
    return f"pid={os.getpid()}\nstarted={time.time():.0f}\n"


def _is_stale_lock(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return True
    owner_pid = _parse_pid(content)
    if owner_pid is not None and not _pid_is_alive(owner_pid):
        return True
    started = _parse_started(content)
    if started is not None and (time.time() - started) > _STALE_LOCK_SECONDS:
        return True
    return False


def _parse_pid(content: str) -> int | None:
    for line in content.splitlines():
        if line.startswith("pid="):
            try:
                return int(line.split("=", 1)[1].strip())
            except ValueError:
                return None
    return None


def _parse_started(content: str) -> float | None:
    for line in content.splitlines():
        if line.startswith("started="):
            try:
                return float(line.split("=", 1)[1].strip())
            except ValueError:
                return None
    return None


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _pid_is_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _pid_is_alive_windows(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)
