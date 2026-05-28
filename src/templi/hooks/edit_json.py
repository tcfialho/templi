"""Executor do hook edit-json."""

from __future__ import annotations

import json
import os
import re

from templi.core.condition_evaluator import evaluate_condition
from templi.core.models import JsonHookChange
from templi.core.template_engine import render_template_string
from templi.utils.file_utils import read_file, write_file

_JSONPATH_TOKEN = re.compile(r"\['([^']*)'\]|([^.\[]+)")


def execute_edit_json_hook(
    hook_path: str,
    changes: list[JsonHookChange],
    plugin_source_dir: str,
    project_dir: str,
    variables: dict,
    *,
    encoding: str = "utf-8",
    indent: str = "  ",
) -> None:
    rendered_path = render_template_string(hook_path, variables).lstrip("/\\")
    target_file = os.path.join(project_dir, rendered_path)

    content = _read_or_empty(target_file)
    document = json.loads(content) if content.strip() else {}

    for change in changes:
        if change.condition and not evaluate_condition(change.condition, variables):
            continue
        if change.when_not_exists and _jsonpath_exists(document, change.when_not_exists, variables):
            continue
        if change.when_exists and not _jsonpath_exists(document, change.when_exists, variables):
            continue
        if not _can_apply_jsonpath(document, change.jsonpath, variables):
            continue
        update_value = _load_update_value(change, plugin_source_dir, variables)
        _apply_json_update(document, change.jsonpath, update_value, variables)

    serialized = json.dumps(document, indent=indent, ensure_ascii=False)
    if content.endswith("\r\n"):
        serialized = serialized.replace("\n", "\r\n")
    if content and not content.endswith("\n"):
        write_file(target_file, serialized)
    else:
        write_file(target_file, serialized + ("\r\n" if content.endswith("\r\n") else "\n"))


def _read_or_empty(path: str) -> str:
    try:
        return read_file(path)
    except OSError:
        return ""


def _load_update_value(
    change: JsonHookChange,
    plugin_source_dir: str,
    variables: dict,
) -> object:
    if change.update_value is not None:
        rendered = render_template_string(change.update_value, variables).strip()
        try:
            return json.loads(rendered)
        except json.JSONDecodeError:
            return rendered
    if not change.update_snippet:
        return {}
    snippet_path = render_template_string(change.update_snippet, variables)
    snippet_path = snippet_path.replace("\\", os.sep)
    full_path = os.path.join(plugin_source_dir, snippet_path)
    raw = read_file(full_path).strip()
    rendered = render_template_string(raw, variables).strip()
    try:
        return json.loads(rendered)
    except json.JSONDecodeError:
        return rendered


def _jsonpath_exists(document: object, jsonpath: str, variables: dict) -> bool:
    return _can_apply_jsonpath(document, jsonpath, variables)


def _can_apply_jsonpath(document: object, jsonpath: str, variables: dict) -> bool:
    try:
        rendered = render_template_string(jsonpath, variables).strip()
        if rendered == "$":
            return isinstance(document, dict)
        tokens = _jsonpath_tokens(jsonpath, variables)
    except ValueError:
        return False
    if not tokens or any(token == "" for token in tokens):
        return False
    try:
        _resolve_jsonpath(document, jsonpath, variables, create_missing=False)
        return True
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def _jsonpath_tokens(jsonpath: str, variables: dict) -> list[str]:
    rendered = render_template_string(jsonpath, variables).strip()
    if rendered == "$":
        return []
    if not rendered.startswith("$."):
        raise ValueError(f"jsonpath inválido: {rendered}")
    tokens = _tokenize_jsonpath(rendered[2:])
    if not tokens:
        raise ValueError(f"jsonpath inválido: {rendered}")
    return tokens


def _apply_json_update(
    document: object,
    jsonpath: str,
    update_value: object,
    variables: dict,
) -> None:
    if render_template_string(jsonpath, variables).strip() == "$":
        if isinstance(document, dict) and isinstance(update_value, dict):
            _deep_merge(document, update_value)
        return

    parent, key = _resolve_jsonpath(document, jsonpath, variables, create_missing=False)
    current = parent[key]

    if isinstance(current, list):
        if isinstance(update_value, list):
            for item in update_value:
                if item not in current:
                    current.append(item)
        elif update_value not in current:
            current.append(update_value)
        return

    if isinstance(current, dict) and isinstance(update_value, dict):
        _deep_merge(current, update_value)
        return

    parent[key] = update_value


def _deep_merge(target: dict, patch: dict) -> None:
    for key, value in patch.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def _resolve_jsonpath(
    document: object,
    jsonpath: str,
    variables: dict,
    *,
    create_missing: bool,
) -> tuple[object, str | int]:
    rendered = render_template_string(jsonpath, variables).strip()
    if rendered == "$":
        return document, ""

    if not rendered.startswith("$."):
        raise ValueError(f"jsonpath inválido: {rendered}")

    tokens = _tokenize_jsonpath(rendered[2:])
    if not tokens:
        raise ValueError(f"jsonpath inválido: {rendered}")

    current = document
    for token in tokens[:-1]:
        current = _traverse_step(current, token, create_missing=create_missing)

    last = tokens[-1]
    if isinstance(current, dict):
        if last not in current:
            if not create_missing:
                raise KeyError(last)
            current[last] = {}
        return current, last

    if isinstance(current, list):
        index = int(last)
        return current, index

    raise TypeError(f"Não é possível navegar jsonpath em {type(current)}")


def _tokenize_jsonpath(path: str) -> list[str]:
    tokens: list[str] = []
    for match in _JSONPATH_TOKEN.finditer(path):
        bracket, plain = match.groups()
        if bracket is not None:
            tokens.append(bracket)
        elif plain:
            tokens.append(plain)
    return tokens


def _traverse_step(current: object, token: str, *, create_missing: bool) -> object:
    if isinstance(current, dict):
        if token not in current:
            if not create_missing:
                raise KeyError(token)
            current[token] = {}
        return current[token]

    if isinstance(current, list):
        index = int(token)
        return current[index]

    raise TypeError(f"Não é possível navegar token '{token}' em {type(current)}")
