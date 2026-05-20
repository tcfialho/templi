"""Engine de templates Jinja2 para renderização de diretórios."""

from __future__ import annotations

import os

from jinja2 import BaseLoader, ChainableUndefined, Environment, UndefinedError

from templi.cli.printer import print_warning
from templi.utils.file_utils import (
    copy_file,
    ensure_directory,
    read_file,
    read_text_or_detect_binary,
    write_file,
)
from templi.utils.jinja_filters import camelcase, kebabcase, pascalcase


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
                copy_file(source_file, target_file)
            else:
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

                if rendered_content.strip():
                    existing = _read_or_empty(target_file)
                    if existing.strip():
                        rendered_content = _merge_template_contents(
                            rendered_content, existing,
                        )

                write_file(target_file, rendered_content)

            created_files.append(target_file)

    return created_files


def _read_or_empty(path: str) -> str:
    """Return file contents or empty string when missing/unreadable."""
    try:
        return read_file(path)
    except OSError:
        return ""


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


def _merge_template_contents(new_content: str, old_content: str) -> str:
    """Merge new template content with existing file content.

    The renderer performs a paragraph-level interleave when a rendered
    template collides with an existing file:
      1. Both contents are split into paragraphs (groups of consecutive
         non-blank lines, separated by blank lines).
      2. For each paragraph index *i*, the new paragraph's lines are
         followed by the old paragraph's lines (raw concatenation,
         preserving original line endings).
      3. Merged paragraph groups are separated by a single blank line.
      4. Remaining paragraphs from the longer source are appended.
    """
    new_paragraphs = _split_into_paragraphs(new_content)
    old_paragraphs = _split_into_paragraphs(old_content)

    # Detect line ending style from the old content
    line_ending = "\r\n" if "\r\n" in old_content else "\n"

    merged_parts: list[str] = []
    max_len = max(len(new_paragraphs), len(old_paragraphs))

    for i in range(max_len):
        if i > 0:
            merged_parts.append(line_ending)  # blank-line separator
        if i < len(new_paragraphs):
            merged_parts.append("".join(new_paragraphs[i]))
        if i < len(old_paragraphs):
            merged_parts.append("".join(old_paragraphs[i]))

    return "".join(merged_parts)


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
