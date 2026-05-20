"""Value-to-string formatting shared between manifest and env-var exports."""

from __future__ import annotations

from typing import Any


def to_export_string(value: Any) -> str:
    """
    Stringify a Python value for manifest and env-var output.

    - list  → comma-joined items
    - bool  → "true" / "false"
    - other → str(value)
    """
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)
