"""Executor do hook edit (manipulação de arquivos existentes)."""

from __future__ import annotations

import os
import re

from templi.core.condition_evaluator import evaluate_condition
from templi.core.models import HookChange
from templi.core.template_engine import render_template_string
from templi.utils.file_utils import read_file, write_file


def execute_edit_hook(
    hook_path: str,
    changes: list[HookChange],
    plugin_source_dir: str,
    project_dir: str,
    variables: dict,
) -> None:
    """
    Executa um hook edit:
    1. Resolve o path do arquivo alvo (renderizado com Jinja)
    2. Lê o arquivo uma única vez
    3. Aplica todas as changes em sequência sobre o conteúdo em memória
    4. Escreve uma única vez no final
    """
    rendered_path = render_template_string(hook_path, variables)
    # Paths em plugin.yaml são relativos a project_dir.
    rendered_path = rendered_path.lstrip("/\\")
    target_file = os.path.join(project_dir, rendered_path)

    content = _read_or_empty(target_file)
    original_content = content

    for change in changes:
        content = _apply_change(content, change, plugin_source_dir, variables)

    if content != original_content:
        write_file(target_file, content)


def _apply_change(
    content: str,
    change: HookChange,
    plugin_source_dir: str,
    variables: dict,
) -> str:
    if change.condition is not None and not evaluate_condition(change.condition, variables):
        return content

    if change.insert_line is not None:
        return _apply_insert(content, change, plugin_source_dir, variables)

    if change.search_string is not None:
        rendered_search = render_template_string(change.search_string, variables)
        if rendered_search not in content:
            return content
        match_pos = content.find(rendered_search)
        return _apply_search_operations(
            content, change, rendered_search, match_pos, plugin_source_dir, variables,
        )

    if change.search_pattern is not None:
        pattern_str = render_template_string(change.search_pattern, variables)
        match = re.search(pattern_str, content)
        if match is None:
            return content
        return _apply_search_operations(
            content, change, match.group(0), match.start(), plugin_source_dir, variables,
        )

    return content


def _apply_insert(
    content: str,
    change: HookChange,
    plugin_source_dir: str,
    variables: dict,
) -> str:
    insert_value = _resolve_value(
        change.insert_value, change.insert_snippet, plugin_source_dir, variables,
    )
    if not insert_value or not _guards_pass(change, content, variables):
        return content

    lines = content.splitlines(keepends=True)
    line_number = change.insert_line

    if line_number == 0:
        return insert_value + content

    if line_number == -1:
        if content and not content.endswith("\n"):
            return content + "\n" + insert_value
        return content + insert_value

    # Para line_number negativos < -1, insere antes da N-ésima linha contada do final.
    # Para positivos, insere antes da linha N (1-indexed).
    if line_number < -1:
        target_index = max(len(lines) + line_number + 1, 0)
    else:
        target_index = min(line_number - 1, len(lines))

    payload = insert_value if insert_value.endswith("\n") else insert_value + "\n"
    lines.insert(target_index, payload)
    return "".join(lines)


def _apply_search_operations(
    content: str,
    change: HookChange,
    matched_text: str,
    match_pos: int,
    plugin_source_dir: str,
    variables: dict,
) -> str:
    """Apply insert-before / insert-after / replace-by relative to a match."""
    if not _guards_pass(change, content, variables):
        return content

    if change.insert_before_value is not None or change.insert_before_snippet is not None:
        insert_value = _resolve_value(
            change.insert_before_value, change.insert_before_snippet,
            plugin_source_dir, variables,
        )
        if insert_value:
            content, match_pos = _insert_before_line(content, match_pos, insert_value)

    if change.insert_after_value is not None or change.insert_after_snippet is not None:
        insert_value = _resolve_value(
            change.insert_after_value, change.insert_after_snippet,
            plugin_source_dir, variables,
        )
        if insert_value:
            content = _insert_after_line(
                content, match_pos, len(matched_text), insert_value,
            )

    if change.replace_by_value is not None or change.replace_by_snippet is not None:
        replace_value = _resolve_value(
            change.replace_by_value, change.replace_by_snippet,
            plugin_source_dir, variables,
        )
        content = content.replace(matched_text, replace_value, 1)

    return content


def _guards_pass(change: HookChange, content: str, variables: dict) -> bool:
    """Avalia guards when.not-exists / when.exists contra o conteúdo atual."""
    if change.when_not_exists:
        guard_str = render_template_string(change.when_not_exists, variables)
        if guard_str in content:
            return False

    if change.when_exists:
        guard_str = render_template_string(change.when_exists, variables)
        if guard_str not in content:
            return False

    return True


def _insert_after_line(
    content: str, match_pos: int, match_len: int, insert_value: str,
) -> str:
    """Insere conteúdo após o fim da LINHA que contém a match (após o \\n)."""
    line_end = content.find("\n", match_pos + match_len)
    if line_end >= 0:
        return content[:line_end + 1] + insert_value + content[line_end + 1:]
    return content + "\n" + insert_value


def _insert_before_line(
    content: str, match_pos: int, insert_value: str,
) -> tuple[str, int]:
    """Insere conteúdo antes do início da LINHA que contém a match.

    Returns: (new_content, shifted_match_pos)
    """
    line_start = content.rfind("\n", 0, match_pos)
    if line_start >= 0:
        prefix_end = line_start + 1
        new_content = content[:prefix_end] + insert_value + content[prefix_end:]
        return new_content, match_pos + len(insert_value)
    return insert_value + content, match_pos + len(insert_value)


def _resolve_value(
    value: str | None,
    snippet_path: str | None,
    plugin_source_dir: str,
    variables: dict,
) -> str:
    """Resolve o conteúdo: direto ou snippet file renderizado com Jinja."""
    if value is not None:
        return render_template_string(value, variables)

    if snippet_path is not None:
        snippet_full_path = os.path.join(plugin_source_dir, snippet_path)
        try:
            snippet_content = read_file(snippet_full_path)
        except OSError:
            return ""
        return render_template_string(snippet_content, variables)

    return ""


def _read_or_empty(target_file: str) -> str:
    """Lê o arquivo ou retorna string vazia se não existir."""
    try:
        return read_file(target_file)
    except OSError:
        return ""
