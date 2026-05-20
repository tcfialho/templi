"""Filtros Jinja2 customizados para templates."""

from __future__ import annotations

import re


def kebabcase(value: str) -> str:
    """PascalCase/camelCase/snake_case → kebab-case."""
    text = str(value)
    # Inserir hífens antes de letras maiúsculas
    text = re.sub(r"(?<!^)(?=[A-Z])", "-", text)
    # Substituir underscores e espaços por hífens
    text = text.replace("_", "-").replace(" ", "-")
    # Colapsar múltiplos hífens
    text = re.sub(r"-+", "-", text)
    return text.lower()


def camelcase(value: str) -> str:
    """kebab-case/snake_case → camelCase."""
    parts = re.split(r"[-_ ]+", str(value))
    if not parts:
        return ""
    return parts[0].lower() + "".join(part.capitalize() for part in parts[1:])


def pascalcase(value: str) -> str:
    """kebab-case/snake_case → PascalCase."""
    parts = re.split(r"[-_ ]+", str(value))
    return "".join(part.capitalize() for part in parts)
