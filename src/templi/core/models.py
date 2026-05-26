"""Modelos de dados tipados para plugin.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Condition:
    """Condição para inputs e hooks."""

    variable: str
    operator: str  # ==, !=, containsAny, notContainsAny
    value: str | list[str]


@dataclass
class PluginInput:
    """Um input definido no plugin.yaml."""

    label: str
    name: str
    type: str  # text, select, multiselect, bool, password
    required: bool = False
    global_input: bool = False  # campo "global" no YAML
    default: Any = None
    description: str = ""
    help_text: str = ""  # campo "help" no YAML
    pattern: str | None = None
    items: list[str] | None = None
    condition: Condition | None = None
    inputs: list[PluginInput] = field(default_factory=list)  # Sub-inputs para type: object


@dataclass
class HookChange:
    """Uma operação dentro de um hook edit."""

    # Insert por linha
    insert_line: int | None = None
    insert_value: str | None = None
    insert_snippet: str | None = None
    # Search
    search_string: str | None = None
    search_snippet: str | None = None
    search_pattern: str | None = None  # regex pattern (alternativa a search_string)
    insert_before_value: str | None = None
    insert_before_snippet: str | None = None
    insert_after_value: str | None = None
    insert_after_snippet: str | None = None
    replace_by_value: str | None = None
    replace_by_snippet: str | None = None
    # Guards
    when_not_exists: str | None = None
    when_not_exists_snippet: str | None = None
    when_exists: str | None = None
    # Condition (change-level, avaliada antes de aplicar a change)
    condition: Condition | None = None


@dataclass
class Hook:
    """Um hook definido no plugin.yaml."""

    type: str  # run-script, run, render-templates, edit
    trigger: str  # before-render, after-render
    # Campos específicos por tipo:
    script: str | None = None  # run-script
    commands: list[str] | None = None  # run
    path: str | None = None  # render-templates, edit
    changes: list[HookChange] | None = None  # edit
    json_changes: list[JsonHookChange] | None = None  # edit-json
    encoding: str | None = None  # encoding do arquivo
    indent: str | None = None  # indentação ao gravar JSON
    condition: Condition | None = None


@dataclass
class JsonHookChange:
    """Uma operação dentro de um hook edit-json."""

    jsonpath: str
    update_snippet: str | None = None
    update_value: str | None = None
    when_not_exists: str | None = None
    when_exists: str | None = None
    condition: Condition | None = None


@dataclass
class PluginMetadata:
    """Metadados do plugin."""

    name: str
    display_name: str
    description: str
    version: str
    picture: str | None = None


@dataclass
class PluginSpec:
    """Especificação do plugin (inputs, hooks, etc.)."""

    type: str  # app | infra
    compatibility: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    single_use: bool = False
    inputs: list[PluginInput] = field(default_factory=list)
    computed_inputs: dict[str, str] = field(default_factory=dict)
    global_computed_inputs: dict[str, str] = field(default_factory=dict)
    hooks: list[Hook] = field(default_factory=list)
    repository: str | None = None


@dataclass
class Plugin:
    """Representação completa de um plugin."""

    schema_version: str
    kind: str
    metadata: PluginMetadata
    spec: PluginSpec
    source_directory: str
    is_legacy_yaml: bool = False
