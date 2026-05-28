"""Regras genéricas de camadas e reconciliação de variáveis entre applies encadeados."""

from __future__ import annotations

from typing import Any


def incoming_extends_inherited(inherited: Any, incoming: Any) -> bool:
    """True quando `incoming` é a mesma referência lógica com sufixo dotted.

    Ex.: manifesto já tem `Acme.App` (global-computed) e o apply atual
    coleta `Acme.App.sln` — o valor estabelecido deve prevalecer para
    templates/hooks, sem acoplar a nomes de inputs de um plugin específico.
    """
    if incoming == inherited:
        return False
    if not isinstance(inherited, str) or not isinstance(incoming, str):
        return False
    if not incoming.startswith(inherited):
        return False
    suffix = incoming[len(inherited):]
    return suffix.startswith(".") and len(suffix) > 1


def reconcile_with_inherited_computed(
    inherited_computed: dict[str, Any],
    variables: dict[str, Any],
) -> None:
    """Prefer manifest global-computed over collected values that only add a suffix."""
    for key, inherited_value in inherited_computed.items():
        if key not in variables:
            continue
        incoming = variables[key]
        if incoming_extends_inherited(inherited_value, incoming):
            variables[key] = inherited_value


def prefer_collected_global_value(
    collected_value: Any,
    inherited_computed: dict[str, Any],
    name: str,
) -> Any:
    inherited_value = inherited_computed.get(name)
    if inherited_value is None:
        return collected_value
    if incoming_extends_inherited(inherited_value, collected_value):
        return inherited_value
    return collected_value
