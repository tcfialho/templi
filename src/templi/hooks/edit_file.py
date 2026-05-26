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
    content = content.replace("\r\n", "\n").replace("\r", "\n")
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

    search_text = _resolve_search_text(change, plugin_source_dir, variables)
    if search_text is not None:
        if search_text not in content:
            return content
        match_pos = content.find(search_text)
        return _apply_search_operations(
            content, change, search_text, match_pos, plugin_source_dir, variables,
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
    if not insert_value or not _guards_pass(change, content, plugin_source_dir, variables):
        return content

    lines = content.splitlines(keepends=True)
    line_number = change.insert_line

    if line_number == 0:
        insert_value = insert_value.lstrip("\n")
        return insert_value + content

    if line_number == -1:
        if not content:
            return insert_value.lstrip("\n")
        trimmed = content.rstrip("\n")
        stripped_insert = insert_value.lstrip("\n")
        if stripped_insert.startswith("*/") and trimmed.endswith("}"):
            return trimmed + stripped_insert
        if insert_value.startswith("\n\n"):
            return trimmed + insert_value
        if insert_value.startswith("\n"):
            if content.endswith("\n"):
                return trimmed + "\n\n" + insert_value.lstrip("\n")
            return trimmed + insert_value
        return trimmed + "\n" + insert_value.lstrip("\n")

    # Negativos < -1: insere antes da N-ésima linha contada do final.
    # Positivos: insere apos a linha N (1-indexed), pulando linhas em branco.
    if line_number < -1:
        target_index = max(len(lines) + line_number, 0)
        payload = insert_value if insert_value.endswith("\n") else insert_value + "\n"
        if (
            target_index < len(lines)
            and lines[target_index].lstrip().startswith("//")
            and payload.lstrip().startswith("//")
        ):
            lines[target_index] = payload.rstrip("\n") + lines[target_index].lstrip("\n")
            return "".join(lines)
        lines.insert(target_index, payload)
        return "".join(lines)
    else:
        target_index = min(line_number, len(lines))
        while target_index < len(lines) and lines[target_index].strip() == "":
            target_index += 1
        if insert_value.startswith("\n"):
            insert_value = insert_value[1:]

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
    if not _guards_pass(change, content, plugin_source_dir, variables):
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


def _guards_pass(
    change: HookChange,
    content: str,
    plugin_source_dir: str,
    variables: dict,
) -> bool:
    """Avalia guards when.not-exists / when.exists contra o conteúdo atual."""
    if change.when_not_exists_snippet:
        guard_text = _resolve_value(
            None, change.when_not_exists_snippet, plugin_source_dir, variables,
        )
        if guard_text and guard_text in content:
            return False

    if change.when_not_exists:
        guard_str = render_template_string(change.when_not_exists, variables)
        if guard_str in content:
            return False

    if change.when_exists:
        guard_str = render_template_string(change.when_exists, variables)
        if guard_str not in content:
            return False

    return True


def _resolve_search_text(
    change: HookChange,
    plugin_source_dir: str,
    variables: dict,
) -> str | None:
    if change.search_string is not None:
        return render_template_string(change.search_string, variables)
    if change.search_snippet is not None:
        return _resolve_value(None, change.search_snippet, plugin_source_dir, variables)
    return None


def _insert_after_line(
    content: str, match_pos: int, match_len: int, insert_value: str,
) -> str:
    """Insere conteúdo após o fim da LINHA que contém a match (após o \\n)."""
    line_end = content.find("\n", match_pos + match_len)
    if line_end < 0:
        if insert_value.startswith("\n"):
            if content and not content.endswith("\n"):
                return content + "\n" + insert_value
            return content + insert_value
        payload = insert_value.lstrip("\n")
        return content + ("\n" if content and not content.endswith("\n") else "") + payload

    insert_at = line_end + 1

    line_start = content.rfind("\n", 0, match_pos)
    prefix_end = line_start + 1 if line_start >= 0 else 0
    previous_line = content[prefix_end:line_end + 1] if line_end >= 0 else content
    if previous_line.rstrip().endswith("}") and insert_value.startswith("\n"):
        insert_value = insert_value.lstrip("\n")

    if (
        insert_value.startswith("\n\n")
        and insert_at + 1 < len(content)
        and content[insert_at : insert_at + 2] == "\n\n"
    ):
        insert_value = insert_value[1:]
    elif (
        insert_value.startswith("\n\n")
        and insert_at < len(content)
        and content[insert_at] == "\n"
        and (insert_at + 1 >= len(content) or content[insert_at + 1] != "\n")
    ):
        insert_value = insert_value[1:]

    if insert_value and not insert_value.endswith("\n"):
        if insert_at >= len(content) or content[insert_at] not in "\r\n":
            insert_value = insert_value + "\n"
        elif insert_value.count("\n") > 1:
            insert_value = insert_value + "\n"

    return content[:insert_at] + insert_value + content[insert_at:]


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
        rendered = render_template_string(value, variables)
        return rendered.replace("\r\n", "\n").replace("\r", "\n")

    if snippet_path is not None:
        rendered_snippet_path = render_template_string(snippet_path, variables)
        rendered_snippet_path = rendered_snippet_path.replace("/", os.sep).replace("\\", os.sep)
        snippet_full_path = os.path.join(plugin_source_dir, rendered_snippet_path)
        try:
            snippet_content = read_file(snippet_full_path)
        except OSError:
            return ""
        snippet_content = snippet_content.replace("\r\n", "\n").replace("\r", "\n")
        return render_template_string(snippet_content, variables)

    return ""


def _read_or_empty(target_file: str) -> str:
    """Lê o arquivo ou retorna string vazia se não existir."""
    try:
        return read_file(target_file)
    except OSError:
        return ""
