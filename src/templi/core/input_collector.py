"""Sistema de coleta de inputs (interativo e não-interativo)."""

from __future__ import annotations

import re
from typing import Any

from templi.core.condition_evaluator import evaluate_condition
from templi.core.models import PluginInput


def collect_inputs(
    inputs: list[PluginInput],
    cli_values: dict[str, str],
    is_non_interactive: bool,
    collected_so_far: dict[str, Any] | None = None,
    inherited_globals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Coleta todos os inputs, respeitando ordem, condições e modo.

    Args:
        inputs: Lista de inputs do plugin.yaml
        cli_values: Valores passados via CLI (--key value)
        is_non_interactive: Se True, não faz prompts
        collected_so_far: Variáveis já coletadas (para avaliação de condições)

    Returns:
        Mapa {name: value}

    Raises:
        ValueError: Se input obrigatório faltando no modo não-interativo
    """
    collected: dict[str, Any] = dict(collected_so_far or {})

    for plugin_input in inputs:
        if not evaluate_condition(plugin_input.condition, collected):
            continue

        # Sub-inputs (type: object) — collect recursively, sharing parent context
        # so sub-inputs can reference previously-collected variables in conditions.
        if plugin_input.inputs:
            if not is_non_interactive:
                print(f"\n--- {plugin_input.label} ---")
            sub_result = collect_inputs(
                inputs=plugin_input.inputs,
                cli_values=cli_values,
                is_non_interactive=is_non_interactive,
                collected_so_far=collected,
            )
            sub_keys = [sub.name for sub in plugin_input.inputs]
            collected[plugin_input.name] = {
                key: sub_result[key] for key in sub_keys if key in sub_result
            }
            continue

        cli_value = cli_values.get(plugin_input.name)

        if cli_value is not None:
            value = _normalize_value(plugin_input, cli_value)
        elif plugin_input.global_input and inherited_globals and plugin_input.name in inherited_globals:
            value = inherited_globals[plugin_input.name]
        elif is_non_interactive:
            if plugin_input.default is not None:
                if isinstance(plugin_input.default, list) and plugin_input.type == "multiselect":
                    value = plugin_input.default
                else:
                    value = _normalize_value(plugin_input, str(plugin_input.default))
            elif plugin_input.required:
                raise ValueError(
                    f"Input obrigatório '{plugin_input.name}' não fornecido no modo não-interativo"
                )
            else:
                continue
        else:
            value = _prompt_user(plugin_input)

        _validate_input(plugin_input, value)
        collected[plugin_input.name] = value

    return collected


def _normalize_value(plugin_input: PluginInput, raw_value: str) -> Any:
    """
    Converte string da CLI para o tipo correto:
    - multiselect: "webapi,worker" → ["webapi", "worker"]
    - bool: "true"/"Sim" → True
    - text com items: mantém string
    - text sem items: mantém string
    """
    if plugin_input.type == "multiselect":
        if isinstance(raw_value, list):
            return raw_value
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    if plugin_input.type == "bool":
        if isinstance(raw_value, bool):
            return raw_value
        return str(raw_value).lower() in ("true", "sim", "yes", "1")

    return raw_value


def _validate_input(plugin_input: PluginInput, value: Any) -> None:
    """
    Valida o input coletado.

    Raises:
        ValueError: Se validação falhar
    """
    # Required
    if plugin_input.required and _is_empty(value):
        raise ValueError(
            f"Input obrigatório '{plugin_input.name}' está vazio"
        )

    # Pattern (apenas text/string)
    if plugin_input.pattern and isinstance(value, str) and value:
        if not re.match(plugin_input.pattern, value):
            raise ValueError(
                f"Input '{plugin_input.name}' não corresponde ao padrão '{plugin_input.pattern}'. "
                f"Valor: '{value}'"
            )

    # Items (apenas select / text com items)
    if plugin_input.items and isinstance(value, str) and value:
        if value not in plugin_input.items:
            raise ValueError(
                f"Input '{plugin_input.name}' deve ser um dos valores: {plugin_input.items}. "
                f"Valor: '{value}'"
            )

    # Items para multiselect
    if plugin_input.items and isinstance(value, list):
        for item in value:
            if item not in plugin_input.items:
                raise ValueError(
                    f"Input '{plugin_input.name}': valor '{item}' não está na lista: {plugin_input.items}"
                )


def _is_empty(value: Any) -> bool:
    """Verifica se o valor é vazio."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _prompt_user(plugin_input: PluginInput) -> Any:
    """
    Exibe prompt interativo via InquirerPy.

    Tipos suportados:
    - text (sem items): input de texto livre
    - text (com items) / select: lista de seleção única
    - multiselect: lista de checkboxes
    - bool: confirmação Sim/Não
    - password: input mascarado
    """
    from InquirerPy import inquirer

    label = plugin_input.label
    default = plugin_input.default
    items = plugin_input.items

    # text com items ou select → seleção única
    if items and plugin_input.type in ("text", "select"):
        return inquirer.select(
            message=label,
            choices=items,
            default=default,
        ).execute()

    # multiselect → checkboxes
    if plugin_input.type == "multiselect":
        default_list = default if isinstance(default, list) else []
        return inquirer.checkbox(
            message=label,
            choices=items or [],
            default=default_list,
        ).execute()

    # bool → confirmação
    if plugin_input.type == "bool":
        default_bool = default in (True, "true", "True", "Sim", "sim")
        return inquirer.confirm(
            message=label,
            default=default_bool,
        ).execute()

    # password → mascarado
    if plugin_input.type == "password":
        return inquirer.secret(
            message=label,
        ).execute()

    # text sem items → texto livre
    return inquirer.text(
        message=label,
        default=str(default) if default is not None else "",
    ).execute()
