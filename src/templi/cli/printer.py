"""Mensagens formatadas para output no terminal."""

import click


WARNING_MESSAGE = (
    "! Aviso: Não há suporte para registrar ou implantar app com plugin aplicado fora do workspace.\n"
    'Caso pretenda registrar/implantar a app, cancele o processo atual. '
    "Garanta que o workspace ativo esteja configurado antes de continuar "
    "e prossiga para criar a infra depois disso."
)


def print_warning_outside_workspace() -> None:
    """Imprime o aviso de aplicação fora de workspace."""
    click.echo(WARNING_MESSAGE)
    click.echo()


def print_applying(plugin_identifier: str) -> None:
    """Imprime '> Aplicando o plugin <name>.'"""
    click.echo(f"> Aplicando o plugin {plugin_identifier}.")


def print_applied(plugin_identifier: str) -> None:
    """Imprime '- Plugin <name> aplicado.'"""
    click.echo(f"- Plugin {plugin_identifier} aplicado.")


def print_error(message: str) -> None:
    """Imprime mensagem de erro formatada."""
    click.echo(f"Erro: {message}", err=True)


def print_warning(message: str) -> None:
    """Imprime mensagem de aviso."""
    click.echo(f"⚠ Aviso: {message}", err=True)
