"""Descobre variáveis referenciadas por um plugin (templates, condições, computed)."""

from __future__ import annotations

import re
from typing import Any

from templi.core.models import Condition, Hook, HookChange, JsonHookChange, Plugin, PluginInput

_TEMPLATE_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)")


def collect_plugin_variable_references(plugin: Plugin) -> set[str]:
    references: set[str] = set()
    spec = plugin.spec

    _scan_value(spec.computed_inputs, references)
    _scan_value(spec.global_computed_inputs, references)

    for hook in spec.hooks:
        _scan_hook(hook, references)

    for plugin_input in spec.inputs:
        _scan_input(plugin_input, references)

    return references


def _scan_input(plugin_input: PluginInput, references: set[str]) -> None:
    if plugin_input.condition:
        _scan_condition(plugin_input.condition, references)
    for nested in plugin_input.inputs:
        _scan_input(nested, references)


def _scan_hook(hook: Hook, references: set[str]) -> None:
    _scan_value(hook.path, references)
    _scan_value(hook.script, references)
    _scan_value(hook.commands, references)
    if hook.condition:
        _scan_condition(hook.condition, references)
    for change in hook.changes or []:
        _scan_hook_change(change, references)
    for change in hook.json_changes or []:
        _scan_json_hook_change(change, references)


def _scan_hook_change(change: HookChange, references: set[str]) -> None:
    if change.condition:
        _scan_condition(change.condition, references)
    _scan_value(
        [
            change.insert_value,
            change.insert_snippet,
            change.search_string,
            change.search_snippet,
            change.search_pattern,
            change.insert_before_value,
            change.insert_before_snippet,
            change.insert_after_value,
            change.insert_after_snippet,
            change.replace_by_value,
            change.replace_by_snippet,
            change.when_not_exists,
            change.when_not_exists_snippet,
            change.when_exists,
        ],
        references,
    )


def _scan_json_hook_change(change: JsonHookChange, references: set[str]) -> None:
    if change.condition:
        _scan_condition(change.condition, references)
    _scan_value(
        [
            change.jsonpath,
            change.update_snippet,
            change.update_value,
            change.when_not_exists,
            change.when_exists,
        ],
        references,
    )


def _scan_condition(condition: Condition, references: set[str]) -> None:
    references.add(condition.variable)


def _scan_value(value: Any, references: set[str]) -> None:
    if isinstance(value, str):
        references.update(_TEMPLATE_VAR_PATTERN.findall(value))
        return
    if isinstance(value, dict):
        for nested in value.values():
            _scan_value(nested, references)
        return
    if isinstance(value, list):
        for nested in value:
            _scan_value(nested, references)
