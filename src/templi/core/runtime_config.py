"""Configuracao runtime do Templi."""

from __future__ import annotations

import os
import re


COMPAT_NAME_ENV = "TEMPLI_COMPAT_NAME"
ENV_PREFIX_ENV = "TEMPLI_ENV_PREFIX"
MANIFEST_DIR_ENV = "TEMPLI_MANIFEST_DIR"
MANIFEST_FILE_ENV = "TEMPLI_MANIFEST_FILE"
DEFAULT_ENV_PREFIX = "TEMPLI"
DEFAULT_MANIFEST_DIR = ".templi"
DEFAULT_MANIFEST_FILE = "manifest.yaml"

_COMPAT_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def get_manifest_dir() -> str:
    """Retorna o diretorio local de estado usado pelo manifesto."""
    manifest_dir = _get_optional_env_value(MANIFEST_DIR_ENV)
    if manifest_dir is not None:
        return manifest_dir

    runtime_name = get_runtime_name()
    return f".{runtime_name.lower()}"


def get_runtime_name() -> str:
    """Retorna o nome runtime configurado para compatibilidade."""
    compat_name = _get_compat_name()
    if compat_name is None:
        return DEFAULT_ENV_PREFIX.lower()
    return compat_name


def build_runtime_env_name(variable_suffix: str) -> str:
    """Monta o nome de variavel runtime com prefixo compativel."""
    return f"{get_env_prefix()}_{variable_suffix}"


def get_env_prefix() -> str:
    """Retorna o prefixo das variaveis runtime injetadas em scripts."""
    env_prefix = _get_optional_env_value(ENV_PREFIX_ENV)
    if env_prefix is None:
        return get_runtime_name().upper()

    _validate_env_name(env_prefix, ENV_PREFIX_ENV)
    return env_prefix.upper()


def is_compat_mode_enabled() -> bool:
    """Indica se um nome runtime foi configurado explicitamente."""
    return _get_compat_name() is not None


def get_manifest_file() -> str:
    """Retorna o nome do arquivo de manifesto compativel com o modo atual."""
    manifest_file = _get_optional_env_value(MANIFEST_FILE_ENV)
    if manifest_file is not None:
        return manifest_file

    if is_compat_mode_enabled():
        return f"{get_runtime_name().lower()}.yaml"
    return DEFAULT_MANIFEST_FILE


def get_manifest_file_candidates() -> tuple[str, ...]:
    """Lista nomes aceitos para leitura, priorizando o formato configurado."""
    manifest_file = get_manifest_file()
    if manifest_file == DEFAULT_MANIFEST_FILE:
        return (manifest_file,)
    return (manifest_file, DEFAULT_MANIFEST_FILE)



def _get_optional_env_value(env_name: str) -> str | None:
    raw_value = os.getenv(env_name)
    if raw_value is None:
        return None

    normalized_value = raw_value.strip()
    if not normalized_value:
        return None
    return normalized_value


def _get_compat_name() -> str | None:
    compat_name = os.getenv(COMPAT_NAME_ENV)
    if compat_name is None:
        return None

    normalized_name = compat_name.strip()
    if not normalized_name:
        return None

    _validate_compat_name(normalized_name)
    return normalized_name


def _validate_compat_name(compat_name: str) -> None:
    if _COMPAT_NAME_PATTERN.fullmatch(compat_name):
        return

    raise ValueError(
        f"{COMPAT_NAME_ENV} deve iniciar com letra e conter apenas letras, "
        "numeros e underscore."
    )


def _validate_env_name(env_name: str, source_env: str) -> None:
    if _ENV_NAME_PATTERN.fullmatch(env_name):
        return

    raise ValueError(
        f"{source_env} deve iniciar com letra ou underscore e conter apenas "
        "letras, numeros e underscore."
    )


