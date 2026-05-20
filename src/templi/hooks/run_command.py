"""Executor do hook run (comandos CLI arbitrários)."""

from __future__ import annotations

import subprocess

from templi.cli.printer import print_error
from templi.core.template_engine import render_template_string


def execute_run_hook(
    commands: list[str],
    project_dir: str,
    variables: dict,
) -> int:
    """
    Executa uma lista de comandos CLI no diretório do projeto.

    Cada comando é renderizado com Jinja2 antes da execução.

    Returns:
        Exit code do último comando ou 0 se todos ok.
    """
    for command_template in commands:
        rendered_command = render_template_string(command_template, variables)

        try:
            result = subprocess.run(
                rendered_command,
                shell=True,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.stdout:
                print(result.stdout, end="")

            if result.returncode != 0:
                if result.stderr:
                    print_error(f"Comando falhou: '{rendered_command}' (exit {result.returncode}): {result.stderr.strip()}")
                return result.returncode

        except subprocess.TimeoutExpired:
            print_error(f"Timeout ao executar comando: '{rendered_command}'")
            return 1
        except OSError as error:
            print_error(f"Erro ao executar comando: '{rendered_command}': {error}")
            return 1

    return 0
