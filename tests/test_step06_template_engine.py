"""Testes do Step 06 — Engine de Templates Jinja2."""

import os
import pytest

from templi.core.template_engine import (
    create_jinja_env,
    render_template_string,
    render_templates_directory,
)
from templi.utils.jinja_filters import camelcase, kebabcase, pascalcase

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ═══════════════════════════════════════════════════════════════════════════════
# CA-06.1-3: Filtros customizados
# ═══════════════════════════════════════════════════════════════════════════════

class TestKebabcase:
    def test_pascal_case(self):
        assert kebabcase("MeuPlugin") == "meu-plugin"

    def test_snake_case(self):
        assert kebabcase("meu_plugin") == "meu-plugin"

    def test_already_kebab(self):
        assert kebabcase("meu-plugin") == "meu-plugin"

    def test_lowercase(self):
        assert kebabcase("teste") == "teste"


class TestCamelcase:
    def test_kebab_case(self):
        assert camelcase("meu-plugin") == "meuPlugin"

    def test_snake_case(self):
        assert camelcase("meu_plugin") == "meuPlugin"


class TestPascalcase:
    def test_kebab_case(self):
        assert pascalcase("meu-plugin") == "MeuPlugin"

    def test_snake_case(self):
        assert pascalcase("meu_plugin") == "MeuPlugin"


# ═══════════════════════════════════════════════════════════════════════════════
# CA-06.4-6: Render string
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderString:
    def test_simple(self):
        result = render_template_string("Hello {{name}}", {"name": "World"})
        assert result == "Hello World"

    def test_with_filter(self):
        result = render_template_string("{{name|lower}}", {"name": "HELLO"})
        assert result == "hello"

    def test_with_custom_filter(self):
        result = render_template_string("{{name|kebabcase}}", {"name": "MeuPlugin"})
        assert result == "meu-plugin"

    def test_with_raw(self):
        template = "prefix-{% raw %}{{preserved}}{% endraw %}-suffix"
        result = render_template_string(template, {})
        assert result == "prefix-{{preserved}}-suffix"

    def test_undefined_variable(self):
        result = render_template_string("{{variavel_que_nao_existe}}", {})
        assert result == ""


# ═══════════════════════════════════════════════════════════════════════════════
# CA-06.7: Render de diretório com renomeação Jinja
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderDirectory:
    def test_directory_rename(self, tmp_path):
        source = tmp_path / "templates"
        (source / "{{nome_projeto}}").mkdir(parents=True)
        (source / "{{nome_projeto}}" / "README.md").write_text("# {{nome_projeto}}")

        target = tmp_path / "output"
        render_templates_directory(str(source), str(target), {"nome_projeto": "meu-app"})

        assert (target / "meu-app").is_dir()
        assert (target / "meu-app" / "README.md").exists()
        assert (target / "meu-app" / "README.md").read_text() == "# meu-app"

    def test_preserves_gitkeep(self, tmp_path):
        source = tmp_path / "templates"
        source.mkdir()
        (source / ".gitkeep").write_text("")

        target = tmp_path / "output"
        render_templates_directory(str(source), str(target), {})

        assert (target / ".gitkeep").exists()

    def test_merges_existing_file_paragraphs(self, tmp_path):
        """When a template collides with an existing file, the renderer does a
        paragraph-level merge (interleave), NOT a simple overwrite."""
        source = tmp_path / "templates"
        source.mkdir()
        (source / "app.txt").write_text("NEW-P1\n\nNEW-P2\n")

        target = tmp_path / "output"
        target.mkdir()
        (target / "app.txt").write_text("OLD-P1\n\nOLD-P2\n")

        render_templates_directory(str(source), str(target), {})
        # Paragraphs are interleaved: new[0]+old[0], new[1]+old[1]
        assert (target / "app.txt").read_text() == "NEW-P1\nOLD-P1\n\nNEW-P2\nOLD-P2\n"

    def test_overwrites_existing_when_new_empty(self, tmp_path):
        """Empty template content writes empty file (no merge)."""
        source = tmp_path / "templates"
        source.mkdir()
        (source / "app.js").write_text("")

        target = tmp_path / "output"
        target.mkdir()
        (target / "app.js").write_text("// ANTIGO")

        render_templates_directory(str(source), str(target), {})
        assert (target / "app.js").read_text() == ""

    def test_returns_created_files(self, tmp_path):
        source = tmp_path / "templates"
        source.mkdir()
        (source / "a.txt").write_text("a")
        (source / "b.txt").write_text("b")

        target = tmp_path / "output"
        files = render_templates_directory(str(source), str(target), {})
        assert len(files) == 2

    def test_missing_source_dir(self, tmp_path):
        target = tmp_path / "output"
        files = render_templates_directory(str(tmp_path / "inexistente"), str(target), {})
        assert files == []

    def test_binary_file_copied(self, tmp_path):
        source = tmp_path / "templates"
        source.mkdir()
        binary_path = source / "image.bin"
        with open(binary_path, "wb") as file_handle:
            file_handle.write(b"\x89PNG\r\n\x00\x1a\n")

        target = tmp_path / "output"
        render_templates_directory(str(source), str(target), {})

        assert (target / "image.bin").exists()
        with open(target / "image.bin", "rb") as file_handle:
            assert file_handle.read() == b"\x89PNG\r\n\x00\x1a\n"


# ═══════════════════════════════════════════════════════════════════════════════
# CA-06.9: Render do plugin-generator-like (templates com dir Jinja no nome)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderPluginGeneratorLike:
    SOURCE = os.path.join(FIXTURES_DIR, "plugin-generator-like", "templates")

    def test_generates_plugin_directory(self, tmp_path):
        variables = {
            "full_plugin_name": "plugin-teste",
            "plugin_description": "Um plugin de teste",
            "plugin_version": "0.0.1",
        }
        render_templates_directory(self.SOURCE, str(tmp_path), variables)

        assert (tmp_path / "plugin-teste").is_dir()
        assert (tmp_path / "plugin-teste" / "plugin.yaml").exists()
        assert (tmp_path / "plugin-teste" / "README.md").exists()

    def test_plugin_yaml_content(self, tmp_path):
        variables = {
            "full_plugin_name": "plugin-teste",
            "plugin_description": "Um plugin de teste",
            "plugin_version": "0.0.1",
        }
        render_templates_directory(self.SOURCE, str(tmp_path), variables)

        plugin_yaml = (tmp_path / "plugin-teste" / "plugin.yaml").read_text()
        assert "plugin-teste" in plugin_yaml
        assert "Um plugin de teste" in plugin_yaml

    def test_readme_content(self, tmp_path):
        variables = {
            "full_plugin_name": "plugin-teste",
            "plugin_description": "Plugin de teste",
            "plugin_version": "1.2.3",
        }
        render_templates_directory(self.SOURCE, str(tmp_path), variables)

        readme = (tmp_path / "plugin-teste" / "README.md").read_text(encoding="utf-8")
        assert "plugin-teste" in readme
        assert "Plugin de teste" in readme
