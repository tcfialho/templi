"""Credenciais HTTPS reutilizando a mesma configuracao do Git (credential.helper)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml

_GIT_CREDENTIAL_TIMEOUT_SEC = 5
_PLUGINS_ROOT_ENV = "TEMPLI_PLUGINS_ROOT"


def stacked_git_config():
    from dulwich.config import StackedConfig

    return StackedConfig.default()


def resolve_https_credentials(url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("https", "http"):
        return None, None
    if parsed.username:
        user = unquote(parsed.username)
        password = unquote(parsed.password) if parsed.password else ""
        return user, password
    filled = _git_credential_fill(url)
    if filled[0] is not None:
        return filled
    stored = _credentials_from_store_file(parsed.scheme, parsed.hostname or "")
    if stored[0] is not None:
        return stored
    return _credentials_from_local_plugin_clone(url)


def porcelain_https_auth(url: str) -> dict[str, str]:
    username, password = resolve_https_credentials(url)
    if username is None and not password:
        return {}
    return {"username": username or "", "password": password or ""}


def porcelain_https_clone_kwargs(url: str) -> dict:
    kwargs: dict = {"config": stacked_git_config()}
    kwargs.update(porcelain_https_auth(url))
    return kwargs


def _credential_fill_input(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        return None
    lines = [f"protocol={parsed.scheme}", f"host={parsed.hostname}"]
    if parsed.port:
        lines.append(f"port={parsed.port}")
    path = parsed.path.lstrip("/")
    if path:
        lines.append(f"path={path}")
    lines.append("")
    return "\n".join(lines)


def _parse_credential_output(stdout: str) -> tuple[str | None, str | None]:
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip()
    username = fields.get("username")
    if not username and not fields.get("password"):
        return None, None
    return username, fields.get("password", "")


def _git_credential_fill(url: str) -> tuple[str | None, str | None]:
    payload = _credential_fill_input(url)
    if payload is None:
        return None, None
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if os.environ.get("CI", "").lower() in ("1", "true", "yes"):
        env.setdefault("GCM_INTERACTIVE", "Never")
    try:
        completed = subprocess.run(
            ["git", "credential", "fill"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=_GIT_CREDENTIAL_TIMEOUT_SEC,
            env=env,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None, None
    return _parse_credential_output(completed.stdout)


def _credentials_from_store_file(
    scheme: str, hostname: str
) -> tuple[str | None, str | None]:
    from dulwich.client import get_credentials_from_store

    for username, password in get_credentials_from_store(scheme, hostname):
        return username, password
    return None, None


def _normalize_repo_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = unquote(parsed.path or "").rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    host = (parsed.hostname or "").lower()
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}{path}"


def _plugin_search_roots() -> list[Path]:
    roots: list[Path] = []
    env_root = os.environ.get(_PLUGINS_ROOT_ENV, "").strip()
    if env_root:
        roots.append(Path(env_root).expanduser())
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "tools" / "templi-parity").is_dir():
            roots.append(candidate.resolve())
            break
    unique: list[Path] = []
    for root in roots:
        if root.is_dir() and root not in unique:
            unique.append(root)
    return unique


def _credentials_from_local_plugin_clone(url: str) -> tuple[str | None, str | None]:
    target = _normalize_repo_url(url)
    for root in _plugin_search_roots():
        for plugin_yaml in root.glob("*/*/plugin.yaml"):
            try:
                data = yaml.safe_load(plugin_yaml.read_text(encoding="utf-8"))
            except OSError:
                continue
            repo = (data.get("spec") or {}).get("repository")
            if not repo or _normalize_repo_url(str(repo)) != target:
                continue
            plugin_dir = plugin_yaml.parent
            if not (plugin_dir / ".git").exists():
                continue
            remote_url = _git_remote_origin_url(plugin_dir)
            if remote_url:
                return _credentials_from_embedded_remote_url(remote_url)
    return None, None


def _git_remote_origin_url(plugin_dir: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(plugin_dir), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    remote = completed.stdout.strip()
    return remote or None


def _credentials_from_embedded_remote_url(url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(url.strip())
    if not parsed.username:
        return None, None
    user = unquote(parsed.username)
    password = unquote(parsed.password) if parsed.password else ""
    if not password and _host_uses_pat_as_password(parsed.hostname):
        return "", user
    return user, password


def _host_uses_pat_as_password(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower()
    return host == "dev.azure.com" or host.endswith(".visualstudio.com")
