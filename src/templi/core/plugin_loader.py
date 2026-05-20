"""Loader e parser do arquivo plugin.yaml."""

from __future__ import annotations

import os
from typing import Any

import yaml

from templi.core.models import (
    Condition,
    Hook,
    HookChange,
    Plugin,
    PluginInput,
    PluginMetadata,
    PluginSpec,
)
from templi.utils.file_utils import read_file

SUPPORTED_SCHEMA_VERSIONS = ("v2", "v3")


def load_plugin(plugin_dir: str) -> Plugin:
    """
    Carrega, valida e retorna um Plugin tipado a partir do diretório.

    Raises:
        FileNotFoundError: Se plugin_dir ou plugin.yaml não existir.
        ValueError: Se o schema-version não for suportado.
    """
    plugin_dir = os.path.abspath(plugin_dir)

    if not os.path.isdir(plugin_dir):
        raise FileNotFoundError(f"Diretório do plugin não encontrado: {plugin_dir}")

    plugin_yaml_path = os.path.join(plugin_dir, "plugin.yaml")
    if not os.path.isfile(plugin_yaml_path):
        raise FileNotFoundError(
            f"Arquivo plugin.yaml não encontrado em {plugin_dir}"
        )

    raw = yaml.safe_load(read_file(plugin_yaml_path))
    return _parse_plugin(raw, plugin_dir)


def _parse_plugin(raw: dict[str, Any], source_directory: str) -> Plugin:
    """Parseia o dict YAML bruto em um Plugin tipado."""
    schema_version = str(raw.get("schema-version", ""))
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(
            f"schema-version '{schema_version}' não suportado. "
            f"Versões suportadas: {SUPPORTED_SCHEMA_VERSIONS}"
        )

    kind = raw.get("kind", "plugin")
    metadata = _parse_metadata(raw.get("metadata", {}))
    spec = _parse_spec(raw.get("spec", {}), source_directory, schema_version)

    return Plugin(
        schema_version=schema_version,
        kind=kind,
        metadata=metadata,
        spec=spec,
        source_directory=source_directory,
    )


def _parse_metadata(raw: dict[str, Any]) -> PluginMetadata:
    """Parseia a seção metadata."""
    return PluginMetadata(
        name=raw.get("name", ""),
        display_name=raw.get("display-name", ""),
        description=raw.get("description", ""),
        version=str(raw.get("version", "")),
        picture=raw.get("picture"),
    )


def _parse_spec(
    raw: dict[str, Any],
    source_directory: str,
    schema_version: str,
) -> PluginSpec:
    """Parseia a seção spec."""
    raw_inputs = raw.get("inputs") or []
    inputs = [_parse_input(raw_input) for raw_input in raw_inputs]

    raw_hooks = raw.get("hooks") or []
    hooks = [_parse_hook(raw_hook) for raw_hook in raw_hooks]

    # NOTE: v2 plugins without hooks rely on the orchestrator's auto-render
    # of templates/ (step 5). We do NOT add a synthetic render-templates hook
    # here to avoid rendering templates twice (which would trigger the
    # paragraph-merge logic and duplicate content).

    computed_inputs = _parse_computed_inputs(raw.get("computed-inputs"))
    global_computed_inputs = _parse_computed_inputs(
        raw.get("global-computed-inputs")
    )

    return PluginSpec(
        type=raw.get("type", "app"),
        compatibility=raw.get("compatibility") or [],
        technologies=raw.get("technologies") or [],
        single_use=bool(raw.get("single-use", False)),
        inputs=inputs,
        computed_inputs=computed_inputs,
        global_computed_inputs=global_computed_inputs,
        hooks=hooks,
        repository=raw.get("repository"),
    )


def _parse_computed_inputs(
    raw: dict[str, Any] | None,
) -> dict[str, str]:
    """Parseia computed-inputs ou global-computed-inputs."""
    if not raw:
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def _parse_input(raw: dict[str, Any]) -> PluginInput:
    """Parseia um input individual."""
    input_type = raw.get("type", "text")
    items = raw.get("items")

    # v2: type text com items funciona como select
    if input_type == "text" and items:
        input_type = "select"  # Normaliza text+items para select

    condition = _parse_condition(raw.get("condition"))

    sub_inputs = raw.get("inputs") or []
    inputs = [_parse_input(sub) for sub in sub_inputs]

    return PluginInput(
        label=raw.get("label", ""),
        name=raw.get("name", ""),
        type=input_type,
        required=bool(raw.get("required", False)),
        global_input=bool(raw.get("global", False)),
        default=raw.get("default"),
        description=raw.get("description", ""),
        help_text=raw.get("help", ""),
        pattern=raw.get("pattern"),
        items=items,
        condition=condition,
        inputs=inputs,
    )


def _parse_condition(raw: dict[str, Any] | None) -> Condition | None:
    """Parseia uma condição (usada em inputs e hooks)."""
    if not raw:
        return None

    variable = raw.get("variable", "")
    operator = raw.get("operator", "==")
    value = raw.get("value", "")

    return Condition(variable=variable, operator=operator, value=value)


def _parse_hook(raw: dict[str, Any]) -> Hook:
    """Parseia um hook individual baseado no tipo."""
    hook_type = raw.get("type", "")
    trigger = raw.get("trigger", "after-render")
    condition = _parse_condition(raw.get("condition"))

    if hook_type == "run-script":
        return Hook(
            type=hook_type,
            trigger=trigger,
            script=raw.get("script"),
            condition=condition,
        )

    if hook_type == "run":
        return Hook(
            type=hook_type,
            trigger=trigger,
            commands=raw.get("commands", []),
            condition=condition,
        )

    if hook_type == "render-templates":
        return Hook(
            type=hook_type,
            trigger=trigger,
            path=raw.get("path"),
            condition=condition,
        )

    if hook_type == "edit":
        raw_changes = raw.get("changes") or []
        changes = [_parse_change(raw_change) for raw_change in raw_changes]
        return Hook(
            type=hook_type,
            trigger=trigger,
            path=raw.get("path"),
            changes=changes,
            encoding=raw.get("encoding"),
            condition=condition,
        )

    # Tipo desconhecido — parsear genericamente
    return Hook(
        type=hook_type,
        trigger=trigger,
        script=raw.get("script"),
        commands=raw.get("commands"),
        path=raw.get("path"),
        condition=condition,
    )


def _parse_change(raw: dict[str, Any]) -> HookChange:
    """Parseia uma change de um hook edit."""
    change = HookChange()

    # Insert por linha
    if "insert" in raw:
        insert_block = raw["insert"]
        change.insert_line = insert_block.get("line")
        change.insert_value = insert_block.get("value")
        change.insert_snippet = insert_block.get("snippet")
        when_block = insert_block.get("when", {})
        change.when_not_exists = when_block.get("not-exists")
        change.when_exists = when_block.get("exists")

    # Search + operação
    if "search" in raw:
        search_block = raw["search"]
        change.search_string = search_block.get("string")
        change.search_pattern = search_block.get("pattern")

        if "insert-before" in search_block:
            insert_before = search_block["insert-before"]
            change.insert_before_value = insert_before.get("value")
            change.insert_before_snippet = insert_before.get("snippet")

        if "insert-after" in search_block:
            insert_after = search_block["insert-after"]
            change.insert_after_value = insert_after.get("value")
            change.insert_after_snippet = insert_after.get("snippet")

        if "replace-by" in search_block:
            replace_by = search_block["replace-by"]
            change.replace_by_value = replace_by.get("value")
            change.replace_by_snippet = replace_by.get("snippet")

        when_block = search_block.get("when", {})
        change.when_not_exists = when_block.get("not-exists")
        change.when_exists = when_block.get("exists")

    # Fallback: when como sibling de insert/search (ao invés de aninhado)
    if change.when_not_exists is None and change.when_exists is None:
        when_block = raw.get("when", {})
        if when_block:
            change.when_not_exists = when_block.get("not-exists")
            change.when_exists = when_block.get("exists")

    # Change-level condition (pode estar dentro de search, insert, ou como sibling)
    raw_condition = None
    if "search" in raw:
        raw_condition = raw["search"].get("condition")
    if raw_condition is None and "insert" in raw:
        raw_condition = raw["insert"].get("condition")
    if raw_condition is None:
        raw_condition = raw.get("condition")
    change.condition = _parse_condition(raw_condition)

    return change
