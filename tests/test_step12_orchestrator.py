"""Testes do Step 12 — Orquestrador (Pipeline Completo)."""

import os
import yaml
import pytest

from templi.core.orchestrator import apply_plugin
from templi.utils.file_utils import write_file

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ═══════════════════════════════════════════════════════════════════════════════
# CA-12.1: Pipeline simples (plugin com 1 input + templates)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSimplePipeline:
    def _create_plugin(self, base_dir):
        """Cria um plugin de teste simples."""
        plugin_dir = os.path.join(str(base_dir), "my-plugin")
        os.makedirs(plugin_dir)

        plugin_yaml = """schema-version: v3
kind: plugin
metadata:
  name: test-simple
  display-name: Test Simple
  description: Simple test plugin
  version: 1.0.0
spec:
  type: app
  inputs:
    - label: Nome
      name: project_name
      type: text
      required: true
  computed-inputs:
    upper_name: "{{project_name|upper}}"
  hooks: []
"""
        write_file(os.path.join(plugin_dir, "plugin.yaml"), plugin_yaml)

        # Templates
        templates_dir = os.path.join(plugin_dir, "templates")
        os.makedirs(templates_dir)
        write_file(
            os.path.join(templates_dir, "README.md"),
            "# {{project_name}}\n\nUpper: {{upper_name}}\n",
        )

        return plugin_dir

    def test_full_pipeline(self, tmp_path):
        plugin_dir = self._create_plugin(tmp_path)
        project_dir = os.path.join(str(tmp_path), "project")
        os.makedirs(project_dir)

        result = apply_plugin(
            plugin_dir=plugin_dir,
            project_dir=project_dir,
            cli_inputs={"project_name": "meu-app"},
            is_non_interactive=True,
        )

        # Computed inputs calculados
        assert result["upper_name"] == "MEU-APP"

        # Template renderizado
        readme = os.path.join(project_dir, "README.md")
        assert os.path.isfile(readme)
        content = open(readme, encoding="utf-8").read()
        assert "# meu-app" in content
        assert "Upper: MEU-APP" in content

        # Manifesto gerado
        manifest = os.path.join(project_dir, ".templi", "manifest.yaml")
        assert os.path.isfile(manifest)
        manifest_data = yaml.safe_load(open(manifest, encoding="utf-8").read())
        assert manifest_data["applied_plugins"][0]["name"] == "test-simple"
        assert manifest_data["applied_plugins"][0]["inputs"]["project_name"] == "meu-app"


# ═══════════════════════════════════════════════════════════════════════════════
# CA-12.2: Pipeline com hooks edit
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineWithEditHook:
    def _create_plugin_with_edit(self, base_dir):
        plugin_dir = os.path.join(str(base_dir), "edit-plugin")
        os.makedirs(plugin_dir)

        plugin_yaml = """schema-version: v3
kind: plugin
metadata:
  name: test-edit
  display-name: Test Edit
  description: Plugin with edit hooks
  version: 1.0.0
spec:
  type: app
  inputs:
    - label: Nome
      name: project_name
      type: text
      required: true
  hooks:
    - type: edit
      trigger: after-render
      path: config.js
      changes:
        - insert:
            line: 0
            value: "// Gerado pelo plugin\\n"
            when:
              not-exists: "// Gerado pelo plugin"
        - search:
            string: "PORT=3000"
            replace-by:
              value: "PORT=8080"
"""
        write_file(os.path.join(plugin_dir, "plugin.yaml"), plugin_yaml)
        return plugin_dir

    def test_edit_hook_applied(self, tmp_path):
        plugin_dir = self._create_plugin_with_edit(tmp_path)
        project_dir = os.path.join(str(tmp_path), "project")
        os.makedirs(project_dir)
        write_file(os.path.join(project_dir, "config.js"), "PORT=3000\n")

        apply_plugin(
            plugin_dir=plugin_dir,
            project_dir=project_dir,
            cli_inputs={"project_name": "test"},
            is_non_interactive=True,
        )

        content = open(os.path.join(project_dir, "config.js"), encoding="utf-8").read()
        assert "// Gerado pelo plugin" in content
        assert "PORT=8080" in content
        assert "PORT=3000" not in content


# ═══════════════════════════════════════════════════════════════════════════════
# CA-12.3: Pipeline com condições em hooks
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineWithConditionalHooks:
    def _create_plugin_conditional(self, base_dir):
        plugin_dir = os.path.join(str(base_dir), "cond-plugin")
        os.makedirs(plugin_dir)

        # Criar snippets para render-templates condicional
        snippet_dir = os.path.join(plugin_dir, "snippets", "avancado")
        os.makedirs(snippet_dir)
        write_file(os.path.join(snippet_dir, "advanced.txt"), "Advanced content\n")

        plugin_yaml = """schema-version: v3
kind: plugin
metadata:
  name: test-conditional
  display-name: Test Conditional
  description: Plugin with conditional hooks
  version: 1.0.0
spec:
  type: app
  inputs:
    - label: Modo
      name: mode
      type: text
      required: true
      items:
        - simples
        - avancado
  hooks:
    - type: render-templates
      trigger: after-render
      path: snippets/avancado
      condition:
        variable: mode
        operator: "=="
        value: avancado
"""
        write_file(os.path.join(plugin_dir, "plugin.yaml"), plugin_yaml)
        return plugin_dir

    def test_conditional_hook_executed(self, tmp_path):
        plugin_dir = self._create_plugin_conditional(tmp_path)
        project_dir = os.path.join(str(tmp_path), "project")
        os.makedirs(project_dir)

        apply_plugin(
            plugin_dir=plugin_dir,
            project_dir=project_dir,
            cli_inputs={"mode": "avancado"},
            is_non_interactive=True,
        )

        assert os.path.isfile(os.path.join(project_dir, "advanced.txt"))

    def test_conditional_hook_skipped(self, tmp_path):
        plugin_dir = self._create_plugin_conditional(tmp_path)
        project_dir = os.path.join(str(tmp_path), "project")
        os.makedirs(project_dir)

        apply_plugin(
            plugin_dir=plugin_dir,
            project_dir=project_dir,
            cli_inputs={"mode": "simples"},
            is_non_interactive=True,
        )

        assert not os.path.exists(os.path.join(project_dir, "advanced.txt"))


# ═══════════════════════════════════════════════════════════════════════════════
# CA-12.4: Pipeline com run hook
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineWithRunHook:
    def _create_plugin_with_run(self, base_dir):
        plugin_dir = os.path.join(str(base_dir), "run-plugin")
        os.makedirs(plugin_dir)

        plugin_yaml = """schema-version: v3
kind: plugin
metadata:
  name: test-run
  display-name: Test Run
  description: Plugin with run hooks
  version: 1.0.0
spec:
  type: app
  inputs: []
  hooks:
    - type: run
      trigger: after-render
      commands:
        - echo "plugin applied"
"""
        write_file(os.path.join(plugin_dir, "plugin.yaml"), plugin_yaml)
        return plugin_dir

    def test_run_hook_executes(self, tmp_path):
        plugin_dir = self._create_plugin_with_run(tmp_path)
        project_dir = os.path.join(str(tmp_path), "project")
        os.makedirs(project_dir)

        # Should not raise
        apply_plugin(
            plugin_dir=plugin_dir,
            project_dir=project_dir,
            cli_inputs={},
            is_non_interactive=True,
        )

        # Manifesto deve existir
        assert os.path.isfile(os.path.join(project_dir, ".templi", "manifest.yaml"))


# ═══════════════════════════════════════════════════════════════════════════════
# CA-12.5: plugin-generator-like — pipeline completo (templates + hooks + manifest)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPluginGeneratorLikePipeline:
    PLUGIN_DIR = os.path.join(FIXTURES_DIR, "plugin-generator-like")

    def test_generates_full_structure(self, tmp_path):
        project_dir = str(tmp_path / "project")
        os.makedirs(project_dir)

        apply_plugin(
            plugin_dir=self.PLUGIN_DIR,
            project_dir=project_dir,
            cli_inputs={
                "plugin_name": "teste",
                "plugin_description": "Plugin de teste",
                "ecosystem": "nodejs",
                "app_types": "webapi,worker",
                "has_secrets": "Nao",
                "has_snippets": "Sim",
                "has_edits": "Nao",
                "has_helm_values": "Nao",
                "has_catalog_info": "Nao",
                "plugin_version": "0.0.1",
                "repository_url": "",
            },
            is_non_interactive=True,
        )

        generated_dir = os.path.join(project_dir, "plugin-teste")
        assert os.path.isdir(generated_dir)
        assert os.path.isfile(os.path.join(generated_dir, "plugin.yaml"))
        assert os.path.isfile(os.path.join(generated_dir, "README.md"))

        assert os.path.isfile(os.path.join(project_dir, ".templi", "manifest.yaml"))

        gen_plugin_yaml = open(os.path.join(generated_dir, "plugin.yaml"), encoding="utf-8").read()
        assert "plugin-teste" in gen_plugin_yaml
        assert "Plugin de teste" in gen_plugin_yaml


# ═══════════════════════════════════════════════════════════════════════════════
# CA-12.6: Reaproveitamento de global-inputs do manifesto entre plugins
# ═══════════════════════════════════════════════════════════════════════════════

class TestInheritedGlobalsBetweenPlugins:
    def _create_plugin_with_global(self, base_dir, name, needs_solution=True):
        plugin_dir = os.path.join(str(base_dir), name)
        os.makedirs(plugin_dir)

        inputs_yaml = f"""
    - label: Solução
      name: solution_name
      type: text
      required: true
      global: true
""" if needs_solution else ""

        plugin_yaml = f"""schema-version: v3
kind: plugin
metadata:
  name: {name}
  display-name: {name}
  description: Test plugin
  version: 1.0.0
spec:
  type: app
  inputs:{inputs_yaml}
  hooks: []
"""
        write_file(os.path.join(plugin_dir, "plugin.yaml"), plugin_yaml)
        return plugin_dir

    def test_second_plugin_reuses_global_from_manifest(self, tmp_path):
        project_dir = os.path.join(str(tmp_path), "project")
        os.makedirs(project_dir)

        plugin_a = self._create_plugin_with_global(tmp_path, "plugin-a")
        plugin_b = self._create_plugin_with_global(tmp_path, "plugin-b")

        apply_plugin(
            plugin_dir=plugin_a,
            project_dir=project_dir,
            cli_inputs={"solution_name": "MinhaSolucao"},
            is_non_interactive=True,
        )

        manifest = os.path.join(project_dir, ".templi", "manifest.yaml")
        assert os.path.isfile(manifest)
        manifest_data = yaml.safe_load(open(manifest, encoding="utf-8").read())
        assert manifest_data["global-inputs"]["solution_name"] == "MinhaSolucao"

        result = apply_plugin(
            plugin_dir=plugin_b,
            project_dir=project_dir,
            cli_inputs={},
            is_non_interactive=True,
        )

        assert result["solution_name"] == "MinhaSolucao"
