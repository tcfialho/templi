"""Executor do hook run-script (scripts Python/Shell)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

from templi.cli.printer import print_error
from templi.core.runtime_config import DEFAULT_ENV_PREFIX, build_runtime_env_name
from templi.utils.value_format import to_export_string


@dataclass
class ScriptHookResult:
    """Resultado de um hook run-script.

    `exit_code` é o código de saída do subprocess. Os 4 dicts refletem o
    estado das categorias de metadata **após** a execução do script (com
    quaisquer mutações que o script tenha feito via `metadata.inputs[...] = ...`
    etc.).
    """

    exit_code: int
    inputs: dict = field(default_factory=dict)
    global_inputs: dict = field(default_factory=dict)
    computed_inputs: dict = field(default_factory=dict)
    global_computed_inputs: dict = field(default_factory=dict)


def execute_run_script_hook(
    script_path: str,
    plugin_source_dir: str,
    project_dir: str,
    variables: dict,
    *,
    inputs: dict | None = None,
    global_inputs: dict | None = None,
    computed_inputs: dict | None = None,
    global_computed_inputs: dict | None = None,
) -> ScriptHookResult:
    """Executa um script Python (ou shell) no contexto do projeto.

    Variáveis disponibilizadas ao script:

    1. **Env vars UPPERCASE** (compat com scripts legados):
       - `<prefix>_PLUGIN_DIR`, `<prefix>_PROJECT_DIR`
       - Todas as chaves de `variables` em UPPERCASE.

    2. **Objeto `metadata`** (via `templateframework.metadata.Metadata` mockado):
       - `metadata.inputs`, `metadata.global_inputs`,
         `metadata.computed_inputs`, `metadata.global_computed_inputs`
       - `metadata.target_path`, `metadata.plugin_path`
       - `metadata.all_inputs()` — merge das 4 categorias.

       O estado é trocado via arquivo JSON temporário cujo caminho é exposto
       em `<prefix>_METADATA_JSON`. Mutações feitas pelo script nos dicts
       acima são propagadas de volta no `ScriptHookResult`.
    """
    full_script_path = os.path.normpath(os.path.join(plugin_source_dir, script_path))

    initial_payload = {
        "inputs": dict(inputs or {}),
        "global_inputs": dict(global_inputs or {}),
        "computed_inputs": dict(computed_inputs or {}),
        "global_computed_inputs": dict(global_computed_inputs or {}),
        "target_path": os.path.abspath(project_dir),
        "plugin_path": os.path.abspath(plugin_source_dir),
    }

    if not os.path.isfile(full_script_path):
        print_error(f"Script não encontrado: {full_script_path}")
        return _result_from(initial_payload, exit_code=1)

    metadata_path = _write_metadata_payload(initial_payload)
    env = _build_environment(plugin_source_dir, project_dir, variables)
    env[build_runtime_env_name("METADATA_JSON")] = metadata_path

    if full_script_path.lower().endswith(".py"):
        runner_path = os.path.join(os.path.dirname(__file__), "script_runner.py")
        cmd = [sys.executable, runner_path, full_script_path]
    else:
        cmd = [sys.executable, full_script_path]

    try:
        completed = subprocess.run(
            cmd,
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.returncode != 0 and completed.stderr:
            print_error(
                f"Script {script_path} falhou (exit {completed.returncode}): "
                f"{completed.stderr.strip()}"
            )
        exit_code = completed.returncode
    except subprocess.TimeoutExpired:
        print_error(f"Timeout ao executar script {script_path}")
        exit_code = 1
    except OSError as error:
        print_error(f"Erro ao executar script {script_path}: {error}")
        exit_code = 1

    final_payload = _read_metadata_payload(metadata_path, fallback=initial_payload)
    _cleanup_metadata_file(metadata_path)

    return _result_from(final_payload, exit_code=exit_code)


def _build_environment(
    plugin_source_dir: str,
    project_dir: str,
    variables: dict,
) -> dict[str, str]:
    """Constrói mapa de variáveis de ambiente para o subprocess."""
    env = os.environ.copy()
    env.pop(f"{DEFAULT_ENV_PREFIX}_PLUGIN_DIR", None)
    env.pop(f"{DEFAULT_ENV_PREFIX}_PROJECT_DIR", None)
    env.pop(f"{DEFAULT_ENV_PREFIX}_METADATA_JSON", None)
    env[build_runtime_env_name("PLUGIN_DIR")] = os.path.abspath(plugin_source_dir)
    env[build_runtime_env_name("PROJECT_DIR")] = os.path.abspath(project_dir)

    for key, value in variables.items():
        env[key.upper()] = to_export_string(value)

    return env


def _write_metadata_payload(payload: dict) -> str:
    fd, path = tempfile.mkstemp(prefix="templi-metadata-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return path


def _read_metadata_payload(path: str, fallback: dict) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return fallback


def _cleanup_metadata_file(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _result_from(payload: dict, *, exit_code: int) -> ScriptHookResult:
    return ScriptHookResult(
        exit_code=exit_code,
        inputs=dict(payload.get("inputs") or {}),
        global_inputs=dict(payload.get("global_inputs") or {}),
        computed_inputs=dict(payload.get("computed_inputs") or {}),
        global_computed_inputs=dict(payload.get("global_computed_inputs") or {}),
    )
