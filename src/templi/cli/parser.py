"""Parser de argumentos CLI extras e inputs JSON."""

import json


def parse_extra_args(extra_args: list[str]) -> dict[str, str]:
    """
    Converte lista de extra args em dicionário.

    Exemplo:
        ['--plugin_name', 'meu-plugin', '--ecosystem', 'dotnet']
        → {'plugin_name': 'meu-plugin', 'ecosystem': 'dotnet'}
    """
    result: dict[str, str] = {}
    index = 0

    while index < len(extra_args):
        current_arg = extra_args[index]

        if not current_arg.startswith("--"):
            index += 1
            continue

        key = current_arg.lstrip("-")

        if index + 1 < len(extra_args) and not extra_args[index + 1].startswith("--"):
            result[key] = extra_args[index + 1]
            index += 2
        else:
            result[key] = ""
            index += 1

    return result


def parse_inputs_json(json_string: str) -> dict[str, str]:
    """
    Parseia uma string JSON contendo inputs.

    Exemplo:
        '{"plugin_name": "meu-plugin", "ecosystem": "dotnet"}'
        → {'plugin_name': 'meu-plugin', 'ecosystem': 'dotnet'}
    """
    if not json_string or not json_string.strip():
        return {}
    return json.loads(json_string)
