"""Avaliador de condições para inputs e hooks de plugins."""

from __future__ import annotations

from templi.core.models import Condition


def evaluate_condition(condition: Condition | None, variables: dict) -> bool:
    """
    Avalia uma condição contra o mapa de variáveis.

    Retorna True se condição é None (sem condição = sempre executa).
    Retorna False se a variável não existe no mapa.
    """
    if condition is None:
        return True

    actual_value = variables.get(condition.variable)

    if actual_value is None:
        return False

    operator = condition.operator
    expected = condition.value

    if operator == "==":
        return _evaluate_equal(actual_value, expected)

    if operator == "!=":
        return not _evaluate_equal(actual_value, expected)

    if operator == "containsAny":
        return _evaluate_contains_any(actual_value, expected)

    if operator == "notContainsAny":
        return not _evaluate_contains_any(actual_value, expected)

    return False


def _normalize_for_comparison(value: object) -> str:
    """Normaliza valor para comparação de string, tratando booleanos."""
    if isinstance(value, bool):
        return str(value).lower()  # True → "true", False → "false"
    text = str(value)
    if text.lower() in ("true", "false"):
        return text.lower()
    return text


def _evaluate_equal(actual: object, expected: object) -> bool:
    """Compara igualdade. Normaliza booleanos para comparação case-insensitive."""
    return _normalize_for_comparison(actual) == _normalize_for_comparison(expected)


def _evaluate_contains_any(actual: object, expected: object) -> bool:
    """
    ContainsAny:
    - Se actual é LISTA: verifica interseção de conjuntos
    - Se actual é STRING: verifica se algum valor expected está contido como substring
    """
    expected_values = _ensure_list(expected)

    if isinstance(actual, list):
        actual_set = set(_normalize_for_comparison(item) for item in actual)
        expected_set = set(_normalize_for_comparison(item) for item in expected_values)
        return bool(actual_set & expected_set)

    actual_str = str(actual)
    return any(str(expected_item) in actual_str for expected_item in expected_values)


def _ensure_list(value: object) -> list:
    """Garante que o valor é uma lista."""
    if isinstance(value, list):
        return value
    return [value]
