"""Configuracao runtime do Templi."""

from __future__ import annotations

import os
import re


COMPAT_NAME_ENV = "TEMPLI_COMPAT_NAME"
DEFAULT_ENV_PREFIX = "TEMPLI"
DEFAULT_MANIFEST_DIR = ".templi"
MANIFEST_FILE = "manifest.yaml"

_COMPAT_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def get_manifest_dir() -> str:
    """Retorna o diretorio local de estado usado pelo manifesto."""
    compat_name = _get_compat_name()
    if compat_name is None:
        return DEFAULT_MANIFEST_DIR

    return f".{compat_name.lower()}"


def build_runtime_env_name(variable_suffix: str) -> str:
    """Monta o nome de variavel runtime com prefixo compativel."""
    return f"{get_env_prefix()}_{variable_suffix}"


def get_env_prefix() -> str:
    """Retorna o prefixo das variaveis runtime injetadas em scripts."""
    compat_name = _get_compat_name()
    if compat_name is None:
        return DEFAULT_ENV_PREFIX

    return compat_name.upper()


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
