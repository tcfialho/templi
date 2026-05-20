"""Testes do Step 02 — Plugin Loader."""

import os
import pytest

from templi.core.plugin_loader import load_plugin

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ═══════════════════════════════════════════════════════════════════════════════
# CA-02.1: Carregar plugin.yaml simples
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadSimplePlugin:
    def test_schema_version(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-simples"))
        assert plugin.schema_version == "v3"

    def test_kind(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-simples"))
        assert plugin.kind == "plugin"

    def test_metadata_name(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-simples"))
        assert plugin.metadata.name == "test-plugin"

    def test_metadata_display_name(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-simples"))
        assert plugin.metadata.display_name == "Test Plugin"

    def test_metadata_version(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-simples"))
        assert plugin.metadata.version == "1.0.0"

    def test_spec_type(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-simples"))
        assert plugin.spec.type == "app"

    def test_single_input(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-simples"))
        assert len(plugin.spec.inputs) == 1
        assert plugin.spec.inputs[0].name == "project_name"
        assert plugin.spec.inputs[0].type == "text"
        assert plugin.spec.inputs[0].required is True

    def test_empty_hooks(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-simples"))
        assert plugin.spec.hooks == []

    def test_source_directory_absolute(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-simples"))
        assert os.path.isabs(plugin.source_directory)


# ═══════════════════════════════════════════════════════════════════════════════
# CA-02.2: Carregar plugin com inputs condicionais
# ═══════════════════════════════════════════════════════════════════════════════

class TestConditionalInputs:
    def test_conditional_input_exists(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-condicoes"))
        conditional_inputs = [i for i in plugin.spec.inputs if i.condition is not None]
        assert len(conditional_inputs) == 2

    def test_equal_condition(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-condicoes"))
        dotnet_input = [i for i in plugin.spec.inputs if i.name == "has_base_plugin"][0]
        assert dotnet_input.condition is not None
        assert dotnet_input.condition.variable == "ecosystem"
        assert dotnet_input.condition.operator == "=="
        assert dotnet_input.condition.value == "dotnet"

    def test_not_equal_condition(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-condicoes"))
        app_types_input = [i for i in plugin.spec.inputs if i.name == "app_types"][0]
        assert app_types_input.condition is not None
        assert app_types_input.condition.operator == "!="
        assert app_types_input.condition.value == "python"

    def test_multiselect_type(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-condicoes"))
        app_types_input = [i for i in plugin.spec.inputs if i.name == "app_types"][0]
        assert app_types_input.type == "multiselect"
        assert app_types_input.items == ["webapi", "worker", "job"]


# ═══════════════════════════════════════════════════════════════════════════════
# CA-02.3: Carregar plugin com todos os tipos de hooks
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllHookTypes:
    def test_hook_types_present(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-completo"))
        hook_types = [h.type for h in plugin.spec.hooks]
        assert "run-script" in hook_types
        assert "render-templates" in hook_types
        assert "edit" in hook_types
        assert "run" in hook_types

    def test_run_script_hook(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-completo"))
        run_script_hooks = [h for h in plugin.spec.hooks if h.type == "run-script"]
        assert len(run_script_hooks) == 1
        assert run_script_hooks[0].script == "./scripts/setup.py"
        assert run_script_hooks[0].trigger == "after-render"

    def test_render_templates_hook_with_condition(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-completo"))
        render_hooks = [h for h in plugin.spec.hooks if h.type == "render-templates"]
        assert len(render_hooks) == 1
        assert render_hooks[0].path == "snippets/WebApi"
        assert render_hooks[0].condition is not None
        assert render_hooks[0].condition.variable == "mode"
        assert render_hooks[0].condition.value == "avancado"

    def test_run_hook(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-completo"))
        run_hooks = [h for h in plugin.spec.hooks if h.type == "run"]
        assert len(run_hooks) == 1
        assert run_hooks[0].commands == ['echo "done"']


# ═══════════════════════════════════════════════════════════════════════════════
# CA-02.4: Hook edit com todas as operações
# ═══════════════════════════════════════════════════════════════════════════════

class TestEditHook:
    def test_edit_hook_exists(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-edits"))
        edit_hooks = [h for h in plugin.spec.hooks if h.type == "edit"]
        assert len(edit_hooks) == 1

    def test_edit_hook_path_with_jinja(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-edits"))
        edit_hook = [h for h in plugin.spec.hooks if h.type == "edit"][0]
        assert edit_hook.path == "{{project_name}}/index.js"

    def test_edit_hook_change_count(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-edits"))
        edit_hook = [h for h in plugin.spec.hooks if h.type == "edit"][0]
        assert len(edit_hook.changes) == 5

    def test_insert_by_line(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-edits"))
        changes = [h for h in plugin.spec.hooks if h.type == "edit"][0].changes
        insert_line_0 = changes[0]
        assert insert_line_0.insert_line == 0
        assert insert_line_0.insert_value == "// Header\n"
        assert insert_line_0.when_not_exists == "// Header"

    def test_insert_with_snippet(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-edits"))
        changes = [h for h in plugin.spec.hooks if h.type == "edit"][0].changes
        insert_snippet = changes[1]
        assert insert_snippet.insert_line == -1
        assert insert_snippet.insert_snippet == "snippets/footer.txt"

    def test_search_insert_before(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-edits"))
        changes = [h for h in plugin.spec.hooks if h.type == "edit"][0].changes
        search_before = changes[2]
        assert search_before.search_string == "const app"
        assert search_before.insert_before_value == "const logger = require('./logger');\n"
        assert search_before.when_not_exists == "const logger"

    def test_search_insert_after(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-edits"))
        changes = [h for h in plugin.spec.hooks if h.type == "edit"][0].changes
        search_after = changes[3]
        assert search_after.search_string == "app.listen"
        assert search_after.insert_after_value == "app.use('/api', router);\n"

    def test_search_replace(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-com-edits"))
        changes = [h for h in plugin.spec.hooks if h.type == "edit"][0].changes
        replace = changes[4]
        assert replace.search_string == "OLD_VALUE"
        assert replace.replace_by_value == "NEW_VALUE"
        assert replace.when_exists == "OLD_VALUE"


# ═══════════════════════════════════════════════════════════════════════════════
# CA-02.5: Computed inputs
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputedInputs:
    def test_computed_inputs_parsed(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-completo"))
        assert "full_plugin_name" in plugin.spec.computed_inputs
        assert plugin.spec.computed_inputs["full_plugin_name"] == "plugin-{{project_name}}"

    def test_global_computed_inputs_parsed(self):
        plugin = load_plugin(os.path.join(FIXTURES_DIR, "plugin-completo"))
        assert "plugin_applied" in plugin.spec.global_computed_inputs


# ═══════════════════════════════════════════════════════════════════════════════
# CA-02.6: Validação — arquivo não encontrado
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidation:
    def test_missing_directory(self):
        with pytest.raises(FileNotFoundError):
            load_plugin("caminho/completamente/inexistente")

    def test_missing_plugin_yaml(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="plugin.yaml"):
            load_plugin(str(tmp_path))

    def test_invalid_schema_version(self):
        with pytest.raises(ValueError, match="schema-version"):
            load_plugin(os.path.join(FIXTURES_DIR, "plugin-schema-invalido"))


# ═══════════════════════════════════════════════════════════════════════════════
# CA-02.8: plugin-generator-like (v3, muitos inputs e hooks, computed, condicional)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPluginGeneratorLike:
    PLUGIN_DIR = os.path.join(FIXTURES_DIR, "plugin-generator-like")

    def test_metadata_name(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert plugin.metadata.name == "plugin-generator"

    def test_input_count(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert len(plugin.spec.inputs) >= 10

    def test_hook_count(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert len(plugin.spec.hooks) >= 5

    def test_computed_input_full_plugin_name(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert "full_plugin_name" in plugin.spec.computed_inputs
        assert plugin.spec.computed_inputs["full_plugin_name"] == "plugin-{{plugin_name}}"

    def test_schema_version_v3(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert plugin.schema_version == "v3"

    def test_has_conditional_inputs(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        conditional_inputs = [i for i in plugin.spec.inputs if i.condition is not None]
        assert len(conditional_inputs) >= 1

    def test_global_computed_plugin_applied(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert "plugin_applied" in plugin.spec.global_computed_inputs


# ═══════════════════════════════════════════════════════════════════════════════
# CA-02.9: plugin-kafka-like (v2, text+items→select, computed scenario, repository)
# ═══════════════════════════════════════════════════════════════════════════════

class TestKafkaLikePlugin:
    PLUGIN_DIR = os.path.join(FIXTURES_DIR, "plugin-kafka-like")

    def test_schema_version_v2(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert plugin.schema_version == "v2"

    def test_metadata_name(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert plugin.metadata.name == "plugin-kafka-nodejs"

    def test_input_count(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert len(plugin.spec.inputs) == 6

    def test_multiple_hooks(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert len(plugin.spec.hooks) >= 6

    def test_computed_input_scenario(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert "scenario" in plugin.spec.computed_inputs
        assert plugin.spec.computed_inputs["scenario"] == "{{catalog_application_type}}{{kafkausecase}}"

    def test_global_computed_plugin_applied(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert "plugin_applied" in plugin.spec.global_computed_inputs

    def test_hooks_have_conditions(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        conditional_hooks = [h for h in plugin.spec.hooks if h.condition is not None]
        assert len(conditional_hooks) >= 5

    def test_repository_field(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert plugin.spec.repository is not None

    def test_text_with_items_parsed_as_select(self):
        """v2: type text com items e normalizado para select pelo loader."""
        plugin = load_plugin(self.PLUGIN_DIR)
        catalog_input = next(i for i in plugin.spec.inputs if i.name == "catalog_application_type")
        assert catalog_input.type == "select"
        assert catalog_input.items == ["webapi", "worker", "job"]
