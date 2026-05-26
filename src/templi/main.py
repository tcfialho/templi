"""Entry point CLI do templi."""

import os
import sys

import click

from templi.cli.parser import parse_extra_args, parse_inputs_json
from templi.cli.printer import (
    print_applied,
    print_applying,
    print_error,
    print_warning_outside_workspace,
)


@click.group()
def cli():
    """Ferramenta para aplicar plugins YAML em projetos."""


@cli.group()
def apply():
    """Aplica conteúdo ao projeto."""


@apply.command(
    "plugin",
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
)
@click.argument("name_or_path")
@click.option("-s", "--skip-warning", is_flag=True, help="Suprime aviso de workspace.")
@click.option("-q", "--non-interactive", is_flag=True, help="Modo não-interativo.")
@click.option("-i", "--inputs-json", type=str, default=None, help="Inputs em formato JSON.")
@click.option(
    "-ar",
    "--automatic-apply-requirements",
    is_flag=True,
    help="Aplica plugins requeridos automaticamente.",
)
@click.option(
    "--no-update-manifest",
    is_flag=True,
    hidden=True,
    help="Não registra o plugin no manifesto local (applies aninhados via hook run).",
)
@click.pass_context
def apply_plugin(ctx, name_or_path, skip_warning, non_interactive, inputs_json, automatic_apply_requirements, no_update_manifest):
    """Aplica um plugin ao projeto atual.

    NAME_OR_PATH é o caminho para o diretório do plugin contendo plugin.yaml.
    """
    try:
        cli_inputs = parse_extra_args(ctx.args)
        if inputs_json:
            cli_inputs.update(parse_inputs_json(inputs_json))

        plugin_yaml_path = os.path.join(name_or_path, "plugin.yaml")
        if not os.path.isfile(plugin_yaml_path):
            raise FileNotFoundError(
                f"Arquivo plugin.yaml não encontrado em {name_or_path}"
            )

        if not skip_warning:
            print_warning_outside_workspace()

        print_applying(name_or_path)

        from templi.core.orchestrator import apply_plugin as do_apply
        do_apply(
            plugin_dir=name_or_path,
            project_dir=os.getcwd(),
            cli_inputs=cli_inputs,
            is_non_interactive=non_interactive,
            persist_manifest=not no_update_manifest,
        )

        print_applied(name_or_path)

    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print_error(str(error))
        sys.exit(1)


if __name__ == "__main__":
    cli()
