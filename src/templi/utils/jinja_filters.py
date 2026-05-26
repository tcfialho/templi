"""Filtros Jinja2 customizados para templates."""

from __future__ import annotations

import re


def kebabcase(value: str) -> str:
    """PascalCase/camelCase/snake_case -> kebab-case."""
    text = str(value)
    text = re.sub(r"(?<!^)(?=[A-Z])", "-", text)
    text = text.replace("_", "-").replace(" ", "-")
    text = re.sub(r"-+", "-", text)
    return text.lower()


def camelcase(value: str) -> str:
    """kebab-case/snake_case -> camelCase."""
    parts = re.split(r"[-_ ]+", str(value))
    if not parts:
        return ""
    return parts[0].lower() + "".join(part.capitalize() for part in parts[1:])


def pascalcase(value: str) -> str:
    """kebab-case/snake_case -> PascalCase."""
    parts = re.split(r"[-_ ]+", str(value))
    return "".join(part.capitalize() for part in parts)


def sequence_join(value, separator=", ") -> str:
    """Compatibilidade: join em string retorna a propria string."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return separator.join(str(item) for item in value)
    return str(value)
