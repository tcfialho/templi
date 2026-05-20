"""Subprocess runner para hooks run-script.

Lê o estado das 4 categorias de metadata (inputs, global_inputs,
computed_inputs, global_computed_inputs) e demais atributos (target_path,
plugin_path) de um arquivo JSON apontado por env var, monta um
`MetadataMock` compatível com `templateframework.metadata.Metadata`,
executa `run(metadata)` do script e grava o estado mutado de volta no
mesmo arquivo para o orchestrator propagar.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock

# Mock templateframework para que scripts que importem
# `templateframework.metadata` rodem sem o runtime original instalado.
mock_tf = MagicMock()
sys.modules["templateframework"] = mock_tf
sys.modules["templateframework.metadata"] = mock_tf


METADATA_JSON_ENV_SUFFIX = "METADATA_JSON"


class MetadataMock:
    """Mock de `templateframework.metadata.Metadata`.

    Expõe as 4 categorias canônicas + `all_inputs()` (merge dos 4) +
    `target_path` / `plugin_path`. Os dicts são mutáveis: scripts podem
    fazer `metadata.global_computed_inputs["x"] = ...` e a mutação é
    persistida ao final.
    """

    def __init__(
        self,
        inputs: dict | None = None,
        global_inputs: dict | None = None,
        computed_inputs: dict | None = None,
        global_computed_inputs: dict | None = None,
        target_path: str = "",
        plugin_path: str = "",
    ) -> None:
        self.inputs = dict(inputs or {})
        self.global_inputs = dict(global_inputs or {})
        self.computed_inputs = dict(computed_inputs or {})
        self.global_computed_inputs = dict(global_computed_inputs or {})
        self.target_path = target_path
        self.plugin_path = plugin_path

    def all_inputs(self) -> dict:
        merged: dict = {}
        merged.update(self.inputs)
        merged.update(self.global_inputs)
        merged.update(self.computed_inputs)
        merged.update(self.global_computed_inputs)
        return merged


mock_tf.Metadata = MetadataMock


def _resolve_metadata_path() -> str | None:
    for key, value in os.environ.items():
        if key.endswith("_" + METADATA_JSON_ENV_SUFFIX):
            return value
    return None


def _load_metadata() -> tuple[MetadataMock, str | None]:
    path = _resolve_metadata_path()
    if not path or not os.path.isfile(path):
        return MetadataMock(), path

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return MetadataMock(), path

    metadata = MetadataMock(
        inputs=data.get("inputs"),
        global_inputs=data.get("global_inputs"),
        computed_inputs=data.get("computed_inputs"),
        global_computed_inputs=data.get("global_computed_inputs"),
        target_path=data.get("target_path", ""),
        plugin_path=data.get("plugin_path", ""),
    )
    return metadata, path


def _persist_metadata(metadata: MetadataMock, path: str | None) -> None:
    if not path:
        return
    payload = {
        "inputs": metadata.inputs,
        "global_inputs": metadata.global_inputs,
        "computed_inputs": metadata.computed_inputs,
        "global_computed_inputs": metadata.global_computed_inputs,
        "target_path": metadata.target_path,
        "plugin_path": metadata.plugin_path,
    }
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
    except OSError:
        pass


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: script_runner.py <script_path>")
        sys.exit(1)

    script_path = sys.argv[1]
    script_name = os.path.basename(script_path).replace(".py", "")

    script_dir = os.path.dirname(os.path.abspath(script_path))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    metadata, metadata_path = _load_metadata()

    try:
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        if not (spec and spec.loader):
            print(f"Error: could not load spec for {script_path}")
            sys.exit(1)

        module = importlib.util.module_from_spec(spec)
        sys.modules[script_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "run"):
            print(f"Warning: function 'run' not found in {script_name}. Script imported only.")
            _persist_metadata(metadata, metadata_path)
            return

        print(f"Executing 'run' from {script_name}...")
        try:
            module.run(metadata)
        except TypeError:
            module.run()

        _persist_metadata(metadata, metadata_path)

    except Exception as error:
        # Persiste o estado parcial para depuração, mas sinaliza falha.
        _persist_metadata(metadata, metadata_path)
        print(f"Error executing script {script_path}: {error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
