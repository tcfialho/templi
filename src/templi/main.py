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
from templi.core.plugin_ref import resolve_plugin_directory


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
    "--subpath",
    default=None,
    help="Subpasta do plugin dentro do caminho local ou do clone Git (monorepo).",
)
@click.option(
    "--git-ref",
    default=None,
    help="Branch ou tag ao clonar repositório Git (NAME_OR_PATH como URL).",
)
@click.pass_context
def apply_plugin(
    ctx,
    name_or_path,
    skip_warning,
    non_interactive,
    inputs_json,
    automatic_apply_requirements,
    subpath,
    git_ref,
):
    """Aplica um plugin ao projeto atual.

    NAME_OR_PATH é pasta local com plugin.yaml ou URL de repositório Git.
    """
    try:
        cli_inputs = parse_extra_args(ctx.args)
        if inputs_json:
            cli_inputs.update(parse_inputs_json(inputs_json))

        plugin_dir = resolve_plugin_directory(
            name_or_path,
            subpath=subpath,
            git_ref=git_ref,
        )

        if not skip_warning:
            print_warning_outside_workspace()

        print_applying(plugin_dir)

        from templi.core.orchestrator import apply_plugin as do_apply

        do_apply(
            plugin_dir=plugin_dir,
            project_dir=os.getcwd(),
            cli_inputs=cli_inputs,
            is_non_interactive=non_interactive,
        )

        print_applied(plugin_dir)

    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print_error(str(error))
        sys.exit(1)


if __name__ == "__main__":
    cli()
