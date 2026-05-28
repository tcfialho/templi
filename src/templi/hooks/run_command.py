"""Executor do hook run (comandos CLI arbitrarios)."""

from __future__ import annotations

import os
import re
import subprocess

from templi.cli.printer import print_error
from templi.core.runtime_config import get_manifest_dir
from templi.core.template_engine import render_template_string


def _windows_shell_command(command: str) -> str:
    """cmd.exe nao trata aspas simples como delimitador; hooks legados usam estilo bash."""
    if os.name != "nt":
        return command
    return re.sub(r"'([^']*)'", r'"\1"', command)


def _normalize_shell_command(command: str) -> str:
    if os.name != "nt":
        return command
    stripped = command.strip()
    state_dir = get_manifest_dir()
    if stripped == f"rm -rf {state_dir}":
        return f'if exist "{state_dir}" rmdir /s /q "{state_dir}"'
    if stripped.startswith("rm -f "):
        target = stripped[6:].strip()
        return f'if exist "{target}" del /f /q "{target}"'
    return command


def execute_run_hook(
    commands: list[str],
    project_dir: str,
    variables: dict,
) -> int:
    """Executa uma lista de comandos CLI no diretorio do projeto."""
    env = os.environ.copy()

    for command_template in commands:
        rendered_command = _windows_shell_command(
            _normalize_shell_command(
                render_template_string(command_template, variables)
            )
        )
        try:
            result = subprocess.run(
                rendered_command,
                shell=True,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )

            if result.stdout:
                print(result.stdout, end="")

            if result.returncode != 0:
                if result.stderr:
                    print_error(
                        f"Comando falhou: '{rendered_command}' "
                        f"(exit {result.returncode}): {result.stderr.strip()}"
                    )
                return result.returncode

        except subprocess.TimeoutExpired:
            print_error(f"Timeout ao executar comando: '{rendered_command}'")
            return 1
        except OSError as error:
            print_error(f"Erro ao executar comando: '{rendered_command}': {error}")
            return 1

    return 0
