"""Resolve plugin directory from local path or Git repository URL."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

PLUGIN_YAML = "plugin.yaml"
_CACHE_ROOT = Path.home() / ".cache" / "templi" / "plugins"


def is_git_reference(ref: str) -> bool:
    normalized = ref.strip()
    return normalized.startswith(("https://", "http://", "git@", "ssh://"))


def resolve_plugin_directory(
    ref: str,
    *,
    subpath: str | None = None,
    git_ref: str | None = None,
    require_plugin_yaml: bool = True,
) -> str:
    """Return absolute path to plugin directory (local or cached Git clone)."""
    ref = ref.strip()
    if not ref:
        raise ValueError("Referência do plugin vazia.")

    if is_git_reference(ref):
        plugin_dir = _plugin_dir_from_git(ref, subpath=subpath, git_ref=git_ref)
    else:
        plugin_dir = Path(ref).expanduser().resolve()
        if subpath:
            plugin_dir = plugin_dir / subpath.strip("/\\")

    if require_plugin_yaml:
        _assert_plugin_yaml(plugin_dir)

    return str(plugin_dir)


def _plugin_dir_from_git(
    url: str,
    *,
    subpath: str | None,
    git_ref: str | None,
) -> Path:
    clone_url = _normalize_remote_url(url)
    clone_root = _cache_dir_for(url, git_ref) / "repo"
    _ensure_synced_clone(clone_url, clone_root, git_ref)

    plugin_dir = clone_root
    if subpath:
        plugin_dir = clone_root / subpath.strip("/\\")
    return plugin_dir.resolve()


def _normalize_remote_url(url: str) -> str:
    if url.startswith(("https://", "http://")):
        return url
    raise ValueError(
        "Somente URLs HTTPS/HTTP são suportadas para plugins remotos. "
        "Ex.: https://dev.azure.com/org/proj/_git/repo"
    )


def _cache_dir_for(url: str, git_ref: str | None) -> Path:
    digest = hashlib.sha256(f"{url}|{git_ref or ''}".encode()).hexdigest()[:16]
    return _CACHE_ROOT / digest


def _ensure_synced_clone(url: str, dest: Path, git_ref: str | None) -> None:
    if _is_git_worktree(dest):
        try:
            _fetch_and_reset(url, dest, git_ref)
            return
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)

    dest.parent.mkdir(parents=True, exist_ok=True)
    _clone_repository(url, dest, git_ref)


def _is_git_worktree(path: Path) -> bool:
    git_dir = path / ".git"
    return git_dir.is_dir() or git_dir.is_file()


def _clone_repository(url: str, dest: Path, git_ref: str | None) -> None:
    from dulwich import porcelain

    from templi.core.git_auth import porcelain_https_clone_kwargs

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    kwargs: dict = {
        "checkout": True,
        "depth": 1,
        **porcelain_https_clone_kwargs(url),
    }
    if git_ref:
        kwargs["branch"] = git_ref

    try:
        porcelain.clone(url, str(dest), **kwargs)
    except Exception as error:
        raise RuntimeError(f"Falha ao clonar repositório: {error}") from error


def _fetch_and_reset(url: str, dest: Path, git_ref: str | None) -> None:
    from dulwich import porcelain

    from templi.core.git_auth import porcelain_https_auth

    porcelain.fetch(
        str(dest),
        remote_location=url,
        depth=1,
        operation="fetch",
        **porcelain_https_auth(url),
    )
    reset_target = _remote_reset_ref(git_ref)
    porcelain.reset(str(dest), "hard", reset_target)


def _remote_reset_ref(git_ref: str | None) -> bytes:
    if git_ref:
        return f"refs/remotes/origin/{git_ref}".encode()
    return b"HEAD"


def _assert_plugin_yaml(plugin_dir: Path) -> None:
    plugin_yaml = plugin_dir / PLUGIN_YAML
    if plugin_yaml.is_file():
        return
    raise FileNotFoundError(
        f"Arquivo {PLUGIN_YAML} não encontrado em {plugin_dir}"
    )
