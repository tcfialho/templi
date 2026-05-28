"""Manifest Manager - cria/atualiza o manifesto local."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import yaml

from templi.core.manifest_lock import is_manifest_write_locked
from templi.core.models import Plugin
from templi.core.runtime_config import (
    get_manifest_dir,
    get_manifest_file,
    get_manifest_file_candidates,
    is_compat_mode_enabled,
)
from templi.utils.file_utils import ensure_directory, read_file, write_file
from templi.utils.value_format import to_export_string


def _format_manifest_input_value(value: Any, *, preserve_lists: bool = False) -> Any:
    if isinstance(value, list):
        if preserve_lists:
            return value
        return ",".join(str(item) for item in value)
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        if value == "Yes":
            return True
        if value == "No":
            return False
    return to_export_string(value)


def _is_configured_manifest_format(manifest: dict) -> bool:
    """Detecta se o manifesto esta no formato schema-version."""
    return manifest.get("schema-version") is not None or manifest.get("kind") == "manifest"


def _load_configured_manifest_format(manifest: dict) -> tuple[dict, dict]:
    """Extrai spec e metadata de um manifesto schema-version."""
    spec = manifest.get("spec") or {}
    metadata = manifest.get("metadata") or {}
    return spec, metadata


def _manifest_plugin_version(version: str) -> str:
    return version if version else "n/a"


def _create_configured_manifest(
    plugin: Plugin,
    collected_inputs: dict[str, Any],
    global_inputs: dict[str, Any] | None,
    global_computed_inputs: dict[str, Any] | None,
) -> dict:
    """Cria um manifesto novo no formato schema-version v2."""
    now = datetime.now(timezone.utc)
    global_keys = set(global_inputs.keys()) if global_inputs else set()
    plugin_inputs = {
        key: _format_manifest_input_value(value, preserve_lists=True)
        for key, value in collected_inputs.items()
        if key not in global_keys
    }
    plugin_entry = {
        "name": f"local/{plugin.metadata.name}@{_manifest_plugin_version(plugin.metadata.version)}",
        "alias": f"{plugin.metadata.name}-{int(now.timestamp() * 1000)}",
        "type": plugin.spec.type if plugin.spec else "app",
        "inputs": plugin_inputs,
        "inputs-envs": {},
        "connections": {"requires": [], "generates": []},
        "links": {"generates": []},
    }

    spec: dict[str, Any] = {
        "type": plugin.spec.type if plugin.spec else "app",
        "plugins": [plugin_entry],
        "global-inputs": dict(global_inputs) if global_inputs else {},
        "global-computed-inputs": (
            dict(global_computed_inputs) if global_computed_inputs else {}
        ),
    }

    return {
        "schema-version": "v2",
        "kind": "manifest",
        "spec": spec,
    }


def _update_configured_manifest(
    existing: dict,
    plugin: Plugin,
    collected_inputs: dict[str, Any],
    global_inputs: dict[str, Any] | None,
    global_computed_inputs: dict[str, Any] | None,
) -> dict:
    """Atualiza um manifesto existente no formato schema-version."""
    now = datetime.now(timezone.utc)
    global_keys = set(global_inputs.keys()) if global_inputs else set()
    plugin_inputs = {
        key: _format_manifest_input_value(value, preserve_lists=True)
        for key, value in collected_inputs.items()
        if key not in global_keys
    }
    plugin_entry = {
        "name": f"local/{plugin.metadata.name}@{_manifest_plugin_version(plugin.metadata.version)}",
        "alias": f"{plugin.metadata.name}-{int(now.timestamp() * 1000)}",
        "type": plugin.spec.type if plugin.spec else "app",
        "inputs": plugin_inputs,
        "inputs-envs": {},
        "connections": {"requires": [], "generates": []},
        "links": {"generates": []},
    }

    spec = existing.get("spec") or {}
    plugins = spec.get("plugins") or []
    plugins.append(plugin_entry)
    spec["plugins"] = plugins

    if global_inputs:
        existing_globals = spec.get("global-inputs") or {}
        existing_globals.update(global_inputs)
        spec["global-inputs"] = existing_globals

    if global_computed_inputs is not None:
        spec["global-computed-inputs"] = dict(global_computed_inputs)

    existing["spec"] = spec
    return existing


def _is_configured_compat_mode() -> bool:
    """Detecta se estamos em modo de compatibilidade configurado."""
    return is_compat_mode_enabled()


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
    - Nome e versao
    - Timestamp
    - Inputs coletados explicitos

    Tambem atualiza global-inputs e global-computed-inputs.

    Em modo de compatibilidade configurado, usa formato schema-v2.

    Returns:
        Caminho absoluto do arquivo gerado.
    """
    manifest_dir = os.path.join(project_dir, get_manifest_dir())
    manifest_file = get_manifest_file()
    manifest_path = os.path.join(manifest_dir, manifest_file)
    ensure_directory(manifest_dir)

    if is_manifest_write_locked(project_dir):
        return manifest_path

    existing_manifest = _load_existing_manifest(manifest_path)
    is_configured_mode = _is_configured_compat_mode()
    is_configured_format = _is_configured_manifest_format(existing_manifest)

    if is_configured_mode or is_configured_format:
        if existing_manifest and is_configured_format:
            new_manifest = _update_configured_manifest(
                existing_manifest,
                plugin,
                collected_inputs,
                global_inputs,
                global_computed_inputs,
            )
        else:
            new_manifest = _create_configured_manifest(
                plugin,
                collected_inputs,
                global_inputs,
                global_computed_inputs,
            )
    else:
        new_manifest = _update_templi_manifest(
            existing_manifest,
            plugin,
            collected_inputs,
            global_inputs,
            global_computed_inputs,
        )

    yaml_content = yaml.dump(
        new_manifest,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    write_file(manifest_path, yaml_content)
    return manifest_path


def _update_templi_manifest(
    existing: dict,
    plugin: Plugin,
    collected_inputs: dict[str, Any],
    global_inputs: dict[str, Any] | None,
    global_computed_inputs: dict[str, Any] | None,
) -> dict:
    """Atualiza um manifesto no formato templi legado."""
    plugin_entry = _build_plugin_entry(plugin, collected_inputs)

    if "applied_plugins" not in existing:
        existing["applied_plugins"] = []

    existing["applied_plugins"].append(plugin_entry)

    if global_inputs:
        existing_globals = existing.get("global-inputs") or {}
        existing_globals.update(global_inputs)
        existing["global-inputs"] = existing_globals

    if global_computed_inputs is not None:
        existing["global-computed-inputs"] = dict(global_computed_inputs)

    return existing


def load_global_layers(project_dir: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Carrega global-inputs e global-computed-inputs separados do manifesto."""
    manifest_dir = os.path.join(project_dir, get_manifest_dir())
    manifest = _load_existing_manifest_from_candidates(manifest_dir)

    global_inputs: dict[str, Any] = {}
    global_computed: dict[str, Any] = {}

    if _is_configured_manifest_format(manifest):
        spec, _ = _load_configured_manifest_format(manifest)
        previous_globals = spec.get("global-inputs")
        if isinstance(previous_globals, dict):
            global_inputs.update(previous_globals)
        previous_computed = spec.get("global-computed-inputs")
        if isinstance(previous_computed, dict):
            global_computed.update(previous_computed)
    else:
        previous_globals = manifest.get("global-inputs")
        if isinstance(previous_globals, dict):
            global_inputs.update(previous_globals)
        previous_computed = manifest.get("global-computed-inputs")
        if isinstance(previous_computed, dict):
            global_computed.update(previous_computed)

    return global_inputs, global_computed


def load_global_inputs(project_dir: str) -> dict[str, Any]:
    """
    Carrega global-inputs e global-computed-inputs do manifesto existente.

    Suporta formato schema-version e formato templi legado.

    Retorna dict combinado com todos os globals disponiveis para
    plugins subsequentes.
    """
    global_inputs, global_computed = load_global_layers(project_dir)
    result: dict[str, Any] = {}
    result.update(global_inputs)
    result.update(global_computed)
    return result


def _load_existing_manifest_from_candidates(manifest_dir: str) -> dict:
    for manifest_file in get_manifest_file_candidates():
        manifest_path = os.path.join(manifest_dir, manifest_file)
        manifest = _load_existing_manifest(manifest_path)
        if manifest:
            return manifest
    return {}


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
    """Constroi a entrada de plugin para o manifesto."""
    entry: dict[str, Any] = {
        "name": plugin.metadata.name,
        "version": plugin.metadata.version,
        "description": plugin.metadata.description,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }

    if collected_inputs:
        entry["inputs"] = {
            key: _format_manifest_input_value(value)
            for key, value in collected_inputs.items()
        }

    return entry
