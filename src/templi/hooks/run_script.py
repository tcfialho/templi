"""Executor do hook run-script (scripts Python/Shell)."""

from __future__ import annotations

import os
import subprocess
import sys

from templi.cli.printer import print_error
from templi.core.runtime_config import DEFAULT_ENV_PREFIX, build_runtime_env_name
from templi.utils.value_format import to_export_string


def execute_run_script_hook(
    script_path: str,
    plugin_source_dir: str,
    project_dir: str,
    variables: dict,
) -> int:
    """
    Executa um script Python no contexto do projeto.

    Variáveis de ambiente injetadas:
    - <prefix>_PLUGIN_DIR: diretório absoluto do plugin
    - <prefix>_PROJECT_DIR: diretório absoluto do projeto
    - Todos os inputs como UPPERCASE
    """
    full_script_path = os.path.normpath(os.path.join(plugin_source_dir, script_path))

    if not os.path.isfile(full_script_path):
        print_error(f"Script não encontrado: {full_script_path}")
        return 1

    env = _build_environment(plugin_source_dir, project_dir, variables)

    if full_script_path.lower().endswith(".py"):
        runner_path = os.path.join(os.path.dirname(__file__), "script_runner.py")
        cmd = [sys.executable, runner_path, full_script_path]
    else:
        cmd = [sys.executable, full_script_path]

    try:
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.stdout:
            print(result.stdout, end="")

        if result.returncode != 0:
            if result.stderr:
                print_error(f"Script {script_path} falhou (exit {result.returncode}): {result.stderr.strip()}")

        return result.returncode

    except subprocess.TimeoutExpired:
        print_error(f"Timeout ao executar script {script_path}")
        return 1
    except OSError as error:
        print_error(f"Erro ao executar script {script_path}: {error}")
        return 1


def _build_environment(
    plugin_source_dir: str,
    project_dir: str,
    variables: dict,
) -> dict[str, str]:
    """Constrói mapa de variáveis de ambiente para o subprocess."""
    env = os.environ.copy()
    env.pop(f"{DEFAULT_ENV_PREFIX}_PLUGIN_DIR", None)
    env.pop(f"{DEFAULT_ENV_PREFIX}_PROJECT_DIR", None)
    env[build_runtime_env_name("PLUGIN_DIR")] = os.path.abspath(plugin_source_dir)
    env[build_runtime_env_name("PROJECT_DIR")] = os.path.abspath(project_dir)

    for key, value in variables.items():
        env[key.upper()] = to_export_string(value)

    return env
