"""Teste específico para inputs aninhados (type: object)."""

from templi.core.models import PluginInput
from templi.core.input_collector import collect_inputs

class TestNestedInputs:
    def test_collect_nested_object_non_interactive(self):
        # Definição do input pai com filhos
        sub1 = PluginInput(name="endpoint", label="Endpoint", type="text", required=True)
        sub2 = PluginInput(name="method", label="Method", type="text", required=True)
        
        parent = PluginInput(
            name="api_config",
            label="API Configuration",
            type="object",
            inputs=[sub1, sub2]
        )

        # Simular CLI values: flattening ou nomes diretos?
        # Pela implementação atual, o sub-input collector recebe o mesmo dict cli_values global.
        # Então se passarmos --endpoint e --method, o sub-collector vai pegar.
        cli_values = {
            "endpoint": "/v1/users",
            "method": "GET"
        }

        collected = collect_inputs(
            inputs=[parent],
            cli_values=cli_values,
            is_non_interactive=True
        )

        # Verificação
        assert "api_config" in collected
        api_config = collected["api_config"]
        assert isinstance(api_config, dict)
        assert api_config["endpoint"] == "/v1/users"
        assert api_config["method"] == "GET"

        # Os inputs filhos TAMBÉM ficam no nível raiz global?
        # Pela implementação:
        # collected[sub.name] será setado no `sub_result` (que é o `collected` do nível pai passado como `collected_so_far`?)
        # Não, `collect_inputs` cria `collected = dict(collected_so_far)`.
        # Então o `sub_result` tem TUDO.
        # Mas o `collected` do nível PAI só recebe o `value` explicitamente no final do loop.
        # PORÉM, `collected_so_far` é passado apenas para LEITURA nas condições.
        # O `collected` retornado pelo nível filho NÃO afeta o `collected` do nível pai diretamente, exceto pelo que extraímos.
        
        # Testar se 'endpoint' vazou para o nível raiz do collected pai
        # Pela implementação, extraímos chaves -> valor pai -> collected[pai].
        # As chaves dos filhos NÃO são adicionadas ao collected raiz explicitamente.
        assert "endpoint" not in collected
