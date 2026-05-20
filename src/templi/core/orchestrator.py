"""Orquestrador - pipeline completo de aplicacao de plugin."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from templi.cli.printer import print_warning
from templi.core.computed_resolver import resolve_computed_inputs
from templi.core.condition_evaluator import evaluate_condition
from templi.core.input_collector import collect_inputs
from templi.core.manifest_manager import load_global_inputs, update_manifest
from templi.core.models import Hook, Plugin
from templi.core.plugin_loader import load_plugin
from templi.core.template_engine import render_templates_directory
from templi.hooks.edit_file import execute_edit_hook
from templi.hooks.render_templates import execute_render_templates_hook
from templi.hooks.run_command import execute_run_hook
from templi.hooks.run_script import ScriptHookResult, execute_run_script_hook


@dataclass
class _VariableState:
    """Estado mutável das 4 categorias + view achatada (`all_variables`).

    Scripts run-script podem alterar quaisquer das 4 categorias; chamamos
    `apply_script_mutations` para reaplicar a mutação no `all_variables`
    (usado por hooks/templates subsequentes) e no namespace `global_inputs`.
    """

    inputs: dict[str, Any] = field(default_factory=dict)
    global_inputs: dict[str, Any] = field(default_factory=dict)
    computed_inputs: dict[str, Any] = field(default_factory=dict)
    global_computed_inputs: dict[str, Any] = field(default_factory=dict)
    all_variables: dict[str, Any] = field(default_factory=dict)

    def apply_script_mutations(self, result: ScriptHookResult) -> None:
        self.inputs.update(result.inputs)
        self.global_inputs.update(result.global_inputs)
        self.computed_inputs.update(result.computed_inputs)
        self.global_computed_inputs.update(result.global_computed_inputs)

        # all_variables é uma view achatada com prioridade: inputs <
        # global_inputs < computed < global_computed (mesma ordem do resolver).
        self.all_variables.update(result.inputs)
        self.all_variables.update(result.global_inputs)
        self.all_variables.update(result.computed_inputs)
        self.all_variables.update(result.global_computed_inputs)
        self.all_variables["global_inputs"] = self.global_inputs


def apply_plugin(
    plugin_dir: str,
    project_dir: str,
    cli_inputs: dict[str, str] | None = None,
    is_non_interactive: bool = False,
) -> dict[str, Any]:
    """
    Pipeline completo de aplicação de um plugin.

    1. Carrega plugin.yaml
    2. Coleta inputs (interativo ou via CLI)
    3. Resolve computed-inputs
    4. Executa hooks before-render
    5. Renderiza templates/
    6. Executa hooks after-render
    7. Atualiza manifesto local

    Returns:
        Dict com todas as variáveis (inputs + computeds), incluindo mutações
        feitas por hooks run-script.
    """
    cli_inputs = cli_inputs or {}
    project_dir = os.path.abspath(project_dir)

    plugin = load_plugin(plugin_dir)
    previous_globals = load_global_inputs(project_dir)

    collected_inputs = collect_inputs(
        inputs=plugin.spec.inputs,
        cli_values=cli_inputs,
        is_non_interactive=is_non_interactive,
    )

    # Layering: previous globals < CLI args < declared inputs.
    merged_variables = {**previous_globals, **cli_inputs, **collected_inputs}
    global_inputs_namespace = _build_global_inputs(
        plugin.spec.inputs, merged_variables,
    )
    merged_variables["global_inputs"] = global_inputs_namespace

    all_variables = resolve_computed_inputs(
        computed_inputs=plugin.spec.computed_inputs,
        global_computed_inputs=plugin.spec.global_computed_inputs,
        variables=merged_variables,
    )

    state = _VariableState(
        inputs=dict(collected_inputs),
        global_inputs=global_inputs_namespace,
        computed_inputs={
            key: all_variables[key]
            for key in plugin.spec.computed_inputs
            if key in all_variables
        },
        global_computed_inputs={
            key: all_variables[key]
            for key in plugin.spec.global_computed_inputs
            if key in all_variables
        },
        all_variables=all_variables,
    )

    _execute_hooks_by_trigger(
        hooks=plugin.spec.hooks,
        trigger="before-render",
        plugin=plugin,
        project_dir=project_dir,
        state=state,
    )

    templates_dir = os.path.join(plugin.source_directory, "templates")
    if os.path.isdir(templates_dir):
        render_templates_directory(templates_dir, project_dir, state.all_variables)

    _execute_hooks_by_trigger(
        hooks=plugin.spec.hooks,
        trigger="after-render",
        plugin=plugin,
        project_dir=project_dir,
        state=state,
    )

    manifest_inputs = {
        key: value for key, value in state.inputs.items()
        if key != "global_inputs"
    }

    update_manifest(
        project_dir, plugin, manifest_inputs,
        global_inputs=state.global_inputs,
        global_computed_inputs=state.global_computed_inputs,
    )

    return state.all_variables


def _execute_hooks_by_trigger(
    hooks: list[Hook],
    trigger: str,
    plugin: Plugin,
    project_dir: str,
    state: _VariableState,
) -> None:
    """Executa todos os hooks com o trigger especificado, respeitando condições."""
    for hook in hooks:
        if hook.trigger != trigger:
            continue
        if not evaluate_condition(hook.condition, state.all_variables):
            continue
        _execute_single_hook(hook, plugin, project_dir, state)


def _execute_single_hook(
    hook: Hook,
    plugin: Plugin,
    project_dir: str,
    state: _VariableState,
) -> None:
    """Executa um único hook baseado no tipo."""
    if hook.type == "render-templates" and hook.path:
        execute_render_templates_hook(
            hook_path=hook.path,
            plugin_source_dir=plugin.source_directory,
            project_dir=project_dir,
            variables=state.all_variables,
        )
        return

    if hook.type == "edit" and hook.path and hook.changes:
        execute_edit_hook(
            hook_path=hook.path,
            changes=hook.changes,
            plugin_source_dir=plugin.source_directory,
            project_dir=project_dir,
            variables=state.all_variables,
        )
        return

    if hook.type == "run-script" and hook.script:
        result = execute_run_script_hook(
            script_path=hook.script,
            plugin_source_dir=plugin.source_directory,
            project_dir=project_dir,
            variables=state.all_variables,
            inputs=state.inputs,
            global_inputs=state.global_inputs,
            computed_inputs=state.computed_inputs,
            global_computed_inputs=state.global_computed_inputs,
        )
        state.apply_script_mutations(result)
        return

    if hook.type == "run" and hook.commands:
        execute_run_hook(
            commands=hook.commands,
            project_dir=project_dir,
            variables=state.all_variables,
        )
        return

    print_warning(f"Hook tipo '{hook.type}' não suportado ou configuração incompleta")


def _build_global_inputs(
    inputs: list,
    collected: dict[str, Any],
) -> dict[str, Any]:
    """Constrói o namespace global_inputs a partir de inputs marcados global: true."""
    global_inputs: dict[str, Any] = {}
    for plugin_input in inputs:
        if plugin_input.global_input and plugin_input.name in collected:
            global_inputs[plugin_input.name] = collected[plugin_input.name]
    return global_inputs
