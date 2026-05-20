"""Testes do Step 04 — Sistema de Coleta de Inputs."""

import os
import pytest

from templi.core.input_collector import collect_inputs
from templi.core.models import Condition, PluginInput
from templi.core.plugin_loader import load_plugin

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ═══════════════════════════════════════════════════════════════════════════════
# CA-04.1: Coleta não-interativa com todos os inputs via CLI
# ═══════════════════════════════════════════════════════════════════════════════

class TestNonInteractiveBasic:
    def test_all_inputs_provided(self):
        inputs = [
            PluginInput(label="Nome", name="plugin_name", type="text", required=True),
            PluginInput(label="Ecossistema", name="ecosystem", type="select", required=True, items=["dotnet", "nodejs"]),
        ]
        cli_values = {"plugin_name": "meu-plugin", "ecosystem": "dotnet"}
        result = collect_inputs(inputs, cli_values, is_non_interactive=True)
        assert result == {"plugin_name": "meu-plugin", "ecosystem": "dotnet"}


# ═══════════════════════════════════════════════════════════════════════════════
# CA-04.2: Erro quando input obrigatório faltando no modo -q
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingRequired:
    def test_missing_required_raises(self):
        inputs = [
            PluginInput(label="Nome", name="plugin_name", type="text", required=True),
        ]
        with pytest.raises(ValueError, match="obrigatório"):
            collect_inputs(inputs, {}, is_non_interactive=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CA-04.3: Default usado quando valor não fornecido
# ═══════════════════════════════════════════════════════════════════════════════

class TestDefaults:
    def test_uses_default(self):
        inputs = [
            PluginInput(label="Versão", name="plugin_version", type="text", required=True, default="0.0.1"),
        ]
        result = collect_inputs(inputs, {}, is_non_interactive=True)
        assert result["plugin_version"] == "0.0.1"

    def test_cli_value_overrides_default(self):
        inputs = [
            PluginInput(label="Versão", name="plugin_version", type="text", required=True, default="0.0.1"),
        ]
        result = collect_inputs(inputs, {"plugin_version": "2.0.0"}, is_non_interactive=True)
        assert result["plugin_version"] == "2.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# CA-04.4: Multiselect parseado de string separada por vírgula
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiselect:
    def test_parse_csv(self):
        inputs = [
            PluginInput(label="Tipos", name="app_types", type="multiselect", required=True, items=["webapi", "worker", "job"]),
        ]
        result = collect_inputs(inputs, {"app_types": "webapi,worker"}, is_non_interactive=True)
        assert result["app_types"] == ["webapi", "worker"]

    def test_parse_single_value(self):
        inputs = [
            PluginInput(label="Tipos", name="app_types", type="multiselect", required=True, items=["webapi", "worker"]),
        ]
        result = collect_inputs(inputs, {"app_types": "webapi"}, is_non_interactive=True)
        assert result["app_types"] == ["webapi"]

    def test_parse_with_spaces(self):
        inputs = [
            PluginInput(label="Tipos", name="app_types", type="multiselect", required=True, items=["webapi", "worker"]),
        ]
        result = collect_inputs(inputs, {"app_types": "webapi, worker"}, is_non_interactive=True)
        assert result["app_types"] == ["webapi", "worker"]


# ═══════════════════════════════════════════════════════════════════════════════
# CA-04.5: Input condicional oculto quando condição falsa
# ═══════════════════════════════════════════════════════════════════════════════

class TestConditionalInputs:
    def test_hidden_when_condition_false(self):
        inputs = [
            PluginInput(label="Ecossistema", name="ecosystem", type="select", required=True, items=["dotnet", "nodejs"]),
            PluginInput(
                label="Plugin base?", name="has_base_plugin", type="select", required=True,
                items=["Sim", "Nao"], default="Nao",
                condition=Condition(variable="ecosystem", operator="==", value="dotnet"),
            ),
        ]
        result = collect_inputs(inputs, {"ecosystem": "nodejs"}, is_non_interactive=True)
        assert "ecosystem" in result
        assert "has_base_plugin" not in result

    def test_visible_when_condition_true(self):
        inputs = [
            PluginInput(label="Ecossistema", name="ecosystem", type="select", required=True, items=["dotnet", "nodejs"]),
            PluginInput(
                label="Plugin base?", name="has_base_plugin", type="select", required=True,
                items=["Sim", "Nao"], default="Nao",
                condition=Condition(variable="ecosystem", operator="==", value="dotnet"),
            ),
        ]
        result = collect_inputs(inputs, {"ecosystem": "dotnet", "has_base_plugin": "Sim"}, is_non_interactive=True)
        assert result["has_base_plugin"] == "Sim"

    def test_chained_conditions(self):
        """Input C depende de B que depende de A."""
        inputs = [
            PluginInput(label="A", name="a", type="text", required=True),
            PluginInput(
                label="B", name="b", type="text", required=True, default="val_b",
                condition=Condition(variable="a", operator="==", value="activate"),
            ),
            PluginInput(
                label="C", name="c", type="text", required=True, default="val_c",
                condition=Condition(variable="b", operator="==", value="val_b"),
            ),
        ]
        # A = "activate" → B visível (default val_b) → C visível (b == val_b)
        result = collect_inputs(inputs, {"a": "activate"}, is_non_interactive=True)
        assert result["b"] == "val_b"
        assert result["c"] == "val_c"

        # A = "skip" → B oculto → C oculto (b não existe)
        result2 = collect_inputs(inputs, {"a": "skip"}, is_non_interactive=True)
        assert "b" not in result2
        assert "c" not in result2


# ═══════════════════════════════════════════════════════════════════════════════
# CA-04.7: Validação de pattern
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatternValidation:
    def test_invalid_pattern_raises(self):
        inputs = [
            PluginInput(
                label="Nome", name="plugin_name", type="text",
                required=True, pattern="^([a-z][a-z0-9]*)(-[a-z0-9]+)*$",
            ),
        ]
        with pytest.raises(ValueError, match="padrão"):
            collect_inputs(inputs, {"plugin_name": "INVALIDO"}, is_non_interactive=True)

    def test_valid_pattern_passes(self):
        inputs = [
            PluginInput(
                label="Nome", name="plugin_name", type="text",
                required=True, pattern="^([a-z][a-z0-9]*)(-[a-z0-9]+)*$",
            ),
        ]
        result = collect_inputs(inputs, {"plugin_name": "meu-plugin"}, is_non_interactive=True)
        assert result["plugin_name"] == "meu-plugin"


# ═══════════════════════════════════════════════════════════════════════════════
# CA-04.8: plugin-generator-like — coleta condicional com 12 inputs
# ═══════════════════════════════════════════════════════════════════════════════

class TestPluginGeneratorLikeInputs:
    PLUGIN_DIR = os.path.join(FIXTURES_DIR, "plugin-generator-like")

    def test_collect_nodejs_hides_base_plugin(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        cli_values = {
            "plugin_name": "teste", "plugin_description": "Teste",
            "ecosystem": "nodejs", "app_types": "webapi,worker",
            "has_secrets": "Nao", "has_snippets": "Sim", "has_edits": "Nao",
            "has_helm_values": "Nao", "has_catalog_info": "Nao",
            "plugin_version": "0.0.1", "repository_url": "",
        }
        result = collect_inputs(plugin.spec.inputs, cli_values, is_non_interactive=True)

        assert result["plugin_name"] == "teste"
        assert result["ecosystem"] == "nodejs"
        assert result["app_types"] == ["webapi", "worker"]
        # has_base_plugin NÃO deve estar (condição: ecosystem == dotnet é falsa)
        assert "has_base_plugin" not in result

    def test_collect_dotnet_shows_base_plugin(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        cli_values = {
            "plugin_name": "teste", "plugin_description": "Teste",
            "ecosystem": "dotnet", "has_base_plugin": "Sim",
            "app_types": "webapi", "has_secrets": "Nao",
            "has_snippets": "Nao", "has_edits": "Nao",
            "has_helm_values": "Nao", "has_catalog_info": "Nao",
            "plugin_version": "0.0.1", "repository_url": "",
        }
        result = collect_inputs(plugin.spec.inputs, cli_values, is_non_interactive=True)
        assert result["ecosystem"] == "dotnet"
        assert "has_base_plugin" in result
        assert result["has_base_plugin"] == "Sim"


# ═══════════════════════════════════════════════════════════════════════════════
# Bool type
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoolInput:
    def test_bool_true_values(self):
        inputs = [PluginInput(label="Debug?", name="debug", type="bool")]
        for true_val in ("true", "True", "Sim", "sim", "yes", "1"):
            result = collect_inputs(inputs, {"debug": true_val}, is_non_interactive=True)
            assert result["debug"] is True

    def test_bool_false_values(self):
        inputs = [PluginInput(label="Debug?", name="debug", type="bool")]
        for false_val in ("false", "False", "Nao", "nao", "no", "0"):
            result = collect_inputs(inputs, {"debug": false_val}, is_non_interactive=True)
            assert result["debug"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# Non-required input omitido no modo não-interativo
# ═══════════════════════════════════════════════════════════════════════════════

class TestOptionalInput:
    def test_optional_input_skipped(self):
        inputs = [
            PluginInput(label="Repo", name="repository_url", type="text", required=False),
        ]
        result = collect_inputs(inputs, {}, is_non_interactive=True)
        assert "repository_url" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# Inherited globals (vindos do manifesto local)  
# ═══════════════════════════════════════════════════════════════════════════════

class TestInheritedGlobals:
    def test_inherited_global_satisfies_required(self):
        """Required + global=true sem CLI mas com inherited deve resolver."""
        inputs = [
            PluginInput(label="Solução", name="solution_name", type="text",
                        required=True, global_input=True),
        ]
        result = collect_inputs(
            inputs, {}, is_non_interactive=True,
            inherited_globals={"solution_name": "MeuCarro"},
        )
        assert result["solution_name"] == "MeuCarro"

    def test_cli_overrides_inherited_global(self):
        """CLI explícito tem precedência sobre inherited do manifesto."""
        inputs = [
            PluginInput(label="Solução", name="solution_name", type="text",
                        required=True, global_input=True),
        ]
        result = collect_inputs(
            inputs, {"solution_name": "NovoValor"}, is_non_interactive=True,
            inherited_globals={"solution_name": "ValorAntigo"},
        )
        assert result["solution_name"] == "NovoValor"

    def test_inherited_ignored_for_non_global_input(self):
        """Input local (global=false) não consome valores herdados; cai no default."""
        inputs = [
            PluginInput(label="Classname", name="classname", type="text",
                        required=True, global_input=False, default="Veiculo"),
        ]
        result = collect_inputs(
            inputs, {}, is_non_interactive=True,
            inherited_globals={"classname": "InvasorIndevido"},
        )
        assert result["classname"] == "Veiculo"

    def test_inherited_required_non_global_still_raises(self):
        """Required sem default e sem CLI, mesmo com inherited (mas global=false), falha."""
        inputs = [
            PluginInput(label="Classname", name="classname", type="text",
                        required=True, global_input=False),
        ]
        with pytest.raises(ValueError, match="obrigatório"):
            collect_inputs(
                inputs, {}, is_non_interactive=True,
                inherited_globals={"classname": "Algo"},
            )

    def test_inherited_preserves_list_type(self):
        """Multiselect com lista python (vinda do manifesto) é preservada — não re-parseada."""
        inputs = [
            PluginInput(label="Operações", name="operations", type="multiselect",
                        required=True, global_input=True,
                        items=["Inserir (POST)", "Obter (GET)", "Alterar (PUT)"]),
        ]
        inherited = {"operations": ["Inserir (POST)", "Obter (GET)"]}
        result = collect_inputs(
            inputs, {}, is_non_interactive=True,
            inherited_globals=inherited,
        )
        assert result["operations"] == ["Inserir (POST)", "Obter (GET)"]

    def test_inherited_preserves_bool_type(self):
        """Bool python (vindo do manifesto) é preservado — sem .lower() em bool."""
        inputs = [
            PluginInput(label="Debug?", name="debug", type="bool",
                        required=True, global_input=True),
        ]
        result = collect_inputs(
            inputs, {}, is_non_interactive=True,
            inherited_globals={"debug": True},
        )
        assert result["debug"] is True

    def test_inherited_global_pattern_still_validates(self):
        """Validação de pattern continua acontecendo mesmo via inherited."""
        inputs = [
            PluginInput(
                label="Nome", name="project_name", type="text",
                required=True, global_input=True,
                pattern="^[a-z][a-z0-9-]*$",
            ),
        ]
        with pytest.raises(ValueError, match="padrão"):
            collect_inputs(
                inputs, {}, is_non_interactive=True,
                inherited_globals={"project_name": "INVALIDO_COM_MAIUSCULA"},
            )

    def test_default_beats_inherited_for_non_global(self):
        """Sanity: input global=false com default usa o default, não o inherited."""
        inputs = [
            PluginInput(label="Versão", name="plugin_version", type="text",
                        required=True, global_input=False, default="0.0.1"),
        ]
        result = collect_inputs(
            inputs, {}, is_non_interactive=True,
            inherited_globals={"plugin_version": "9.9.9"},
        )
        assert result["plugin_version"] == "0.0.1"
