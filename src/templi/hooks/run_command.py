"""Executor do hook run (comandos CLI arbitrarios)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from templi.cli.printer import print_error
from templi.core.runtime_config import (
    get_apply_plugin_command_aliases,
    get_manifest_dir,
    get_plugin_directory_family,
    get_plugin_namespace,
    get_plugins_root_env_name,
)
from templi.core.template_engine import render_template_string


def _command_alias_expression() -> str:
    aliases = sorted(get_apply_plugin_command_aliases(), key=len, reverse=True)
    return "|".join(re.escape(alias) for alias in aliases)


def _external_plugin_reference_pattern() -> re.Pattern[str]:
    namespace = re.escape(get_plugin_namespace())
    return re.compile(
        rf"(?:{_command_alias_expression()})\s+{namespace}/"
        r"(?:(?P<stack>[\w-]+)(?:@[^/]+)?/)?"
        r"(?P<name>[\w-]+)"
        r"(?:@[^\s'\"]+)?",
    )


def _plugin_apply_command_pattern() -> re.Pattern[str]:
    return re.compile(
        rf"^(?:{_command_alias_expression()})\s+"
        r'(?:"(?P<qpath>[^"]+)"|(?P<path>\S+))'
        r"(?P<rest>.*)$",
    )


def _resolve_plugin_dir(plugins_root: str, stack: str | None, name: str) -> str | None:
    if stack:
        direct = os.path.join(plugins_root, stack, name)
        if os.path.isfile(os.path.join(direct, "plugin.yaml")):
            return direct

    root = Path(plugins_root)
    family_prefix = get_plugin_directory_family()
    candidates: list[Path] = []
    for pattern in (f"*/{name}/plugin.yaml", f"*/{family_prefix}-*/{name}/plugin.yaml"):
        candidates.extend(path.parent for path in root.glob(pattern))

    if not candidates:
        return None

    if stack:
        for candidate in candidates:
            if candidate.parent.name == stack:
                return str(candidate)

    if len(candidates) == 1:
        return str(candidates[0])

    return str(sorted(candidates, key=lambda path: str(path))[0])


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


def _rewrite_nested_plugin_apply(command: str) -> str:
    plugins_root = os.environ.get(get_plugins_root_env_name())
    if not plugins_root:
        return command

    def _replace(match: re.Match[str]) -> str:
        plugin_dir = _resolve_plugin_dir(
            plugins_root,
            match.group("stack"),
            match.group("name"),
        )
        if plugin_dir is None:
            return match.group(0)
        return f'python -m templi.main apply plugin "{plugin_dir}"'

    return _external_plugin_reference_pattern().sub(_replace, command)


def _plugin_apply_argv(command: str) -> list[str] | None:
    match = _plugin_apply_command_pattern().match(command.strip())
    if match is None:
        return None

    plugin_path = match.group("qpath") or match.group("path")
    argv = [sys.executable, "-m", "templi.main", "apply", "plugin", plugin_path]
    argv.extend(_parse_cli_tokens(match.group("rest")))
    return argv


def _parse_cli_tokens(rest: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    rest = rest.strip()
    while index < len(rest):
        if rest[index].isspace():
            index += 1
            continue
        if rest.startswith("--", index):
            end = index + 2
            while end < len(rest) and rest[end] not in " ='\"":
                end += 1
            tokens.append(rest[index:end])
            index = end
            if index < len(rest) and rest[index] == "=":
                index += 1
            if index >= len(rest) or rest[index].isspace():
                continue
            value, index = _read_cli_value(rest, index)
            tokens.append(value)
            continue
        if rest[index] == "-":
            end = index + 1
            while end < len(rest) and not rest[end].isspace():
                end += 1
            tokens.append(rest[index:end])
            index = end
            continue
        value, index = _read_cli_value(rest, index)
        tokens.append(value)
    return tokens


def _read_cli_value(rest: str, index: int) -> tuple[str, int]:
    if index >= len(rest):
        return "", index
    if rest[index] in "'\"":
        quote = rest[index]
        start = index + 1
        end = start
        while end < len(rest) and rest[end] != quote:
            end += 1
        return rest[start:end], min(end + 1, len(rest))
    start = index
    while index < len(rest) and not rest[index].isspace():
        index += 1
    return rest[start:index], index


def execute_run_hook(
    commands: list[str],
    project_dir: str,
    variables: dict,
) -> int:
    """
    Executa uma lista de comandos CLI no diretorio do projeto.

    Cada comando e renderizado com Jinja2 antes da execucao.

    Returns:
        Exit code do ultimo comando ou 0 se todos ok.
    """
    env = os.environ.copy()

    for command_template in commands:
        rendered_command = _rewrite_nested_plugin_apply(
            _normalize_shell_command(render_template_string(command_template, variables)),
        )

        try:
            argv = _plugin_apply_argv(rendered_command)
            if argv is not None:
                if "--no-update-manifest" not in argv:
                    argv.append("--no-update-manifest")
                result = subprocess.run(
                    argv,
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env=env,
                )
            else:
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
