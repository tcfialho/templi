"""Executor do hook render-templates."""

from __future__ import annotations

import os

from templi.core.template_engine import render_template_string, render_templates_directory



def execute_render_templates_hook(
    hook_path: str,
    plugin_source_dir: str,
    project_dir: str,
    variables: dict,
) -> list[str]:
    """
    Executa um hook render-templates:
    1. Resolve hook_path relativo ao diretório do plugin
    2. Renderiza variáveis Jinja nos nomes e conteúdos
    3. Copia para o projeto alvo

    Returns:
        Lista de arquivos criados.
    """
    rendered_hook_path = render_template_string(hook_path, variables)
    source_dir = os.path.join(plugin_source_dir, rendered_hook_path.replace("/", os.sep))
    return render_templates_directory(source_dir, project_dir, variables)
