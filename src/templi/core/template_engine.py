"""Engine de templates Jinja2 para renderização de diretórios."""

from __future__ import annotations

import os
import re

from jinja2 import BaseLoader, ChainableUndefined, Environment, UndefinedError

from templi.cli.printer import print_warning
from templi.utils.file_utils import (
    copy_file,
    ensure_directory,
    read_file,
    read_text_or_detect_binary,
    write_file,
)
from templi.utils.jinja_filters import camelcase, kebabcase, pascalcase, sequence_join


def create_jinja_env() -> Environment:
    """
    Cria Environment Jinja2 configurado com:
    - Filtros customizados (kebabcase, camelcase, pascalcase)
    - ChainableUndefined (variáveis undefined → "")
    """
    env = Environment(
        loader=BaseLoader(),
        undefined=ChainableUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["kebabcase"] = kebabcase
    env.filters["camelcase"] = camelcase
    env.filters["pascalcase"] = pascalcase
    env.filters["join"] = sequence_join
    return env


def render_template_string(
    template_str: str,
    variables: dict,
    env: Environment | None = None,
) -> str:
    """Renderiza uma string Jinja2 com as variáveis fornecidas."""
    if env is None:
        env = create_jinja_env()
    return env.from_string(template_str).render(variables)


def render_templates_directory(
    source_dir: str,
    target_dir: str,
    variables: dict,
) -> list[str]:
    """
    Copia todos os arquivos/diretórios de source_dir para target_dir,
    processando nomes e conteúdos com Jinja2.

    Retorna lista de arquivos criados/modificados.
    """
    env = create_jinja_env()
    created_files: list[str] = []

    if not os.path.isdir(source_dir):
        return created_files

    for root, _directories, filenames in os.walk(source_dir):
        relative_root = os.path.relpath(root, source_dir)
        if relative_root == ".":
            target_subdir = target_dir
        else:
            target_subdir = os.path.join(
                target_dir, _render_path_components(relative_root, variables, env),
            )
        ensure_directory(target_subdir)

        for filename in filenames:
            source_file = os.path.join(root, filename)
            rendered_filename = render_template_string(filename, variables, env)
            target_file = os.path.join(target_subdir, rendered_filename)

            content = read_text_or_detect_binary(source_file)
            if content is None:
                if os.path.isfile(target_file):
                    continue
                copy_file(source_file, target_file)
                created_files.append(target_file)
                continue

            try:
                rendered_content = render_template_string(content, variables, env)
            except UndefinedError as exc:
                rel_name = os.path.relpath(source_file, source_dir)
                print_warning(
                    f"Erro ao avaliar a sintaxe Jinja: '{exc}'.\n"
                    f"  Detalhes: {exc}.\n"
                    f"  Verifique a sintaxe para evitar problemas inesperados."
                )
                raise SystemExit(
                    f"ERRO: Fail to use jinja at file: {rel_name} message: {exc}"
                ) from exc

            existing = _read_or_empty(target_file)

            if not rendered_content.strip():
                if not existing.strip():
                    write_file(target_file, "")
                    created_files.append(target_file)
                continue

            if existing.strip():
                if rendered_content.strip() in existing:
                    continue
                if _content_lines_contained_in(rendered_content, existing):
                    continue
                merged = _merge_template_contents(
                    rendered_content, existing,
                )
                if _merge_would_duplicate_yaml_documents(merged):
                    continue
                if _has_duplicate_public_types(merged):
                    rendered_content = rendered_content
                else:
                    rendered_content = merged

            if existing.strip() and target_file.endswith(".cs"):
                rendered_content = _preserve_extra_usings(rendered_content, existing)

            write_file(target_file, rendered_content)
            created_files.append(target_file)

    return created_files


def _read_or_empty(path: str) -> str:
    """Return file contents or empty string when missing/unreadable."""
    try:
        return read_file(path)
    except OSError:
        return ""


def _preserve_extra_usings(new_content: str, old_content: str) -> str:
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    old_usings = [
        (index, line) for index, line in enumerate(old_lines)
        if line.strip().startswith("using ")
    ]
    missing = [
        (index, line) for index, line in old_usings
        if line not in new_content
    ]
    if not missing:
        return new_content

    result = list(new_lines)
    for old_index, using_line in missing:
        insert_at = 0
        for previous_index, previous_line in old_usings:
            if previous_index >= old_index:
                break
            if previous_line in result:
                insert_at = result.index(previous_line) + 1
        result.insert(insert_at, using_line)

    line_ending = "\r\n" if "\r\n" in new_content else "\n"
    merged = line_ending.join(result)
    if new_content.endswith(("\n", "\r\n")):
        merged += line_ending
    return merged


def _split_into_paragraphs(content: str) -> list[list[str]]:
    """Split content into paragraphs (groups of consecutive non-blank lines).

    Each line retains its original line ending (\\r\\n or \\n).
    A blank line is any line whose stripped content is empty.
    """
    lines = content.splitlines(keepends=True)
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip() == "":
            if current:
                paragraphs.append(current)
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(current)
    return paragraphs


def _paragraph_to_text(paragraph_lines: list[str]) -> str:
    return "".join(paragraph_lines).rstrip("\r\n")


def _join_paragraph_blocks(
    paragraphs: list[list[str]],
    line_ending: str,
) -> str:
    blocks = [_paragraph_to_text(block) for block in paragraphs if block]
    return (line_ending * 2).join(blocks)


def _merge_paragraph_blocks(
    new_block: str,
    old_block: str,
    line_ending: str,
) -> str:
    if new_block == old_block or old_block.startswith(new_block):
        return old_block
    if new_block.startswith(old_block):
        return new_block
    if old_block.startswith("- "):
        return f"{new_block.rstrip()}{line_ending}{old_block}"
    return f"{new_block}{line_ending}{old_block}"


def _merge_template_contents(new_content: str, old_content: str) -> str:
    """Interleave template paragraphs with existing file paragraphs."""
    if not old_content.strip():
        return new_content
    if not new_content.strip():
        return old_content

    new_paragraphs = _split_into_paragraphs(new_content)
    old_paragraphs = _split_into_paragraphs(old_content)
    line_ending = "\r\n" if "\r\n" in old_content or "\r\n" in new_content else "\n"

    if len(new_paragraphs) != len(old_paragraphs):
        merged_blocks: list[str] = []
        total = max(len(new_paragraphs), len(old_paragraphs))
        for index in range(total):
            new_block = (
                _paragraph_to_text(new_paragraphs[index])
                if index < len(new_paragraphs)
                else ""
            )
            old_block = (
                _paragraph_to_text(old_paragraphs[index])
                if index < len(old_paragraphs)
                else ""
            )
            if new_block and old_block:
                if index == 0 and len(old_paragraphs) == 1:
                    if new_block == old_block or old_block.startswith(new_block):
                        merged_blocks.append(old_block)
                    elif new_block.startswith(old_block):
                        merged_blocks.append(new_block)
                    else:
                        merged_blocks.append(
                            f"{old_block}{line_ending}{new_block}",
                        )
                else:
                    merged_blocks.append(
                        _merge_paragraph_blocks(new_block, old_block, line_ending),
                    )
            elif new_block:
                merged_blocks.append(new_block)
            elif old_block:
                merged_blocks.append(old_block)

        separator = line_ending * 2
        merged = separator.join(merged_blocks)
        if new_content.endswith(("\n", "\r\n")) or old_content.endswith(("\n", "\r\n")):
            merged += line_ending
        return merged

    merged_blocks: list[str] = []
    total = max(len(new_paragraphs), len(old_paragraphs))
    for index in range(total):
        new_block = (
            _paragraph_to_text(new_paragraphs[index])
            if index < len(new_paragraphs)
            else ""
        )
        old_block = (
            _paragraph_to_text(old_paragraphs[index])
            if index < len(old_paragraphs)
            else ""
        )
        if new_block and old_block:
            merged_blocks.append(
                _merge_paragraph_blocks(new_block, old_block, line_ending),
            )
        elif new_block:
            merged_blocks.append(new_block)
        else:
            merged_blocks.append(old_block)

    separator = line_ending * 2
    merged = separator.join(merged_blocks)
    if new_content.endswith(("\n", "\r\n")) or old_content.endswith(("\n", "\r\n")):
        merged += line_ending
    return merged


def _content_lines_contained_in(new_content: str, old_content: str) -> bool:
    """Return True when every non-empty line of new_content exists in old_content."""
    old_lines = {line.rstrip() for line in old_content.splitlines() if line.strip()}
    return all(
        line.rstrip() in old_lines
        for line in new_content.splitlines()
        if line.strip()
    )


def _merge_would_duplicate_yaml_documents(content: str) -> bool:
    return content.lstrip().count("apiVersion:") > 1


def _has_duplicate_public_types(content: str) -> bool:
    type_names = re.findall(r"public\s+(?:static\s+)?class\s+(\w+)", content)
    return len(type_names) != len(set(type_names))


def _render_path_components(
    relative_path: str,
    variables: dict,
    env: Environment,
) -> str:
    """Renderiza cada componente do path com Jinja2."""
    components = relative_path.replace("\\", "/").split("/")
    rendered_components = [
        render_template_string(component, variables, env) for component in components
    ]
    return os.path.join(*rendered_components)
