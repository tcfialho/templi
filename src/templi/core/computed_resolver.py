"""Resolver de computed-inputs e global-computed-inputs."""

from __future__ import annotations

from templi.core.template_engine import create_jinja_env


def resolve_computed_inputs(
    computed_inputs: dict[str, str],
    global_computed_inputs: dict[str, str],
    variables: dict,
) -> dict:
    """
    Calcula computed-inputs e global-computed-inputs usando Jinja2.

    Ordem:
    1. computed-inputs (podem referenciar inputs + computeds anteriores)
    2. global-computed-inputs (podem referenciar tudo acima)

    Retorna mapa completo (variables + todos os computeds).
    """
    env = create_jinja_env()
    result = dict(variables)

    # plugin_applied e uma variavel interna sempre disponivel.
    if "plugin_applied" not in result:
        result["plugin_applied"] = ""

    for key, template_expression in computed_inputs.items():
        result[key] = env.from_string(template_expression).render(result)

    for key, template_expression in global_computed_inputs.items():
        result[key] = env.from_string(template_expression).render(result)

    return result
