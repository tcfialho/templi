"""Manifest Manager - cria/atualiza o manifesto local."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import yaml

from templi.core.models import Plugin
from templi.core.runtime_config import MANIFEST_FILE, get_manifest_dir
from templi.utils.file_utils import ensure_directory, read_file, write_file
from templi.utils.value_format import to_export_string


def update_manifest(
    project_dir: str,
    plugin: Plugin,
    collected_inputs: dict[str, Any],
    global_inputs: dict[str, Any] | None = None,
    global_computed_inputs: dict[str, Any] | None = None,
) -> str:
    """
    Cria ou atualiza o manifesto local no projeto.

    Adiciona uma entrada de plugin aplicado com:
    - Nome e versão
    - Timestamp
    - Inputs coletados (explícitos)

    Também atualiza global-inputs e global-computed-inputs.

    Returns:
        Caminho absoluto do arquivo gerado.
    """
    manifest_dir = os.path.join(project_dir, get_manifest_dir())
    manifest_path = os.path.join(manifest_dir, MANIFEST_FILE)
    ensure_directory(manifest_dir)

    existing_manifest = _load_existing_manifest(manifest_path)

    plugin_entry = _build_plugin_entry(plugin, collected_inputs)

    if "applied_plugins" not in existing_manifest:
        existing_manifest["applied_plugins"] = []

    existing_manifest["applied_plugins"].append(plugin_entry)

    if global_inputs:
        existing_globals = existing_manifest.get("global-inputs") or {}
        existing_globals.update(global_inputs)
        existing_manifest["global-inputs"] = existing_globals

    if global_computed_inputs:
        existing_computed = existing_manifest.get("global-computed-inputs") or {}
        existing_computed.update(global_computed_inputs)
        existing_manifest["global-computed-inputs"] = existing_computed

    yaml_content = yaml.dump(
        existing_manifest,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    write_file(manifest_path, yaml_content)
    return manifest_path


def load_global_inputs(project_dir: str) -> dict[str, Any]:
    """
    Carrega global-inputs e global-computed-inputs do manifesto existente.

    Retorna dict combinado com todos os globals disponíveis para
    plugins subsequentes.
    """
    manifest_path = os.path.join(project_dir, get_manifest_dir(), MANIFEST_FILE)
    manifest = _load_existing_manifest(manifest_path)

    result: dict[str, Any] = {}

    previous_globals = manifest.get("global-inputs")
    if isinstance(previous_globals, dict):
        result.update(previous_globals)

    previous_computed = manifest.get("global-computed-inputs")
    if isinstance(previous_computed, dict):
        result.update(previous_computed)

    return result


def _load_existing_manifest(manifest_path: str) -> dict:
    """Carrega manifesto existente ou retorna dict vazio."""
    if not os.path.isfile(manifest_path):
        return {}

    try:
        content = read_file(manifest_path)
        loaded = yaml.safe_load(content)
        return loaded if isinstance(loaded, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}


def _build_plugin_entry(
    plugin: Plugin,
    collected_inputs: dict[str, Any],
) -> dict:
    """Constrói a entrada de plugin para o manifesto."""
    entry: dict[str, Any] = {
        "name": plugin.metadata.name,
        "version": plugin.metadata.version,
        "description": plugin.metadata.description,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }

    if collected_inputs:
        entry["inputs"] = {
            key: to_export_string(value) for key, value in collected_inputs.items()
        }

    return entry
