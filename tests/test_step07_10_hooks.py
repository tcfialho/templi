"""Testes dos Steps 07-10 — Hook Executors."""

import os
import pytest

from templi.hooks.render_templates import execute_render_templates_hook
from templi.hooks.edit_file import execute_edit_hook
from templi.hooks.run_command import execute_run_hook
from templi.core.models import HookChange


# ═══════════════════════════════════════════════════════════════════════════════
# Step 07: render-templates
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderTemplatesHook:
    def test_copies_and_renders(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        snippets = plugin_dir / "snippets" / "WebApi"
        snippets.mkdir(parents=True)
        (snippets / "{{name}}.js").write_text('const {{name}} = "{{name}}";')

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        files = execute_render_templates_hook(
            hook_path="snippets/WebApi",
            plugin_source_dir=str(plugin_dir),
            project_dir=str(project_dir),
            variables={"name": "kafka"},
        )

        assert len(files) == 1
        assert (project_dir / "kafka.js").exists()
        assert 'const kafka = "kafka";' in (project_dir / "kafka.js").read_text()

    def test_missing_path(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        files = execute_render_templates_hook(
            hook_path="snippets/Inexistente",
            plugin_source_dir=str(tmp_path / "plugin"),
            project_dir=str(project_dir),
            variables={},
        )
        assert files == []


# ═══════════════════════════════════════════════════════════════════════════════
# Step 08: edit
# ═══════════════════════════════════════════════════════════════════════════════

class TestEditHookInsertByLine:
    def test_insert_at_beginning(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("const app = express();\n")

        changes = [HookChange(insert_line=0, insert_value="// Header\n")]
        execute_edit_hook("app.js", changes, str(tmp_path), str(project_dir), {})

        content = (project_dir / "app.js").read_text()
        assert content.startswith("// Header\n")

    def test_insert_at_end(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("const app = express();\n")

        changes = [HookChange(insert_line=-1, insert_value="module.exports = app;\n")]
        execute_edit_hook("app.js", changes, str(tmp_path), str(project_dir), {})

        content = (project_dir / "app.js").read_text()
        assert content.endswith("module.exports = app;\n")

    def test_insert_guard_not_exists_blocks(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("// Header\nconst app = express();\n")

        changes = [HookChange(insert_line=0, insert_value="// Header\n", when_not_exists="// Header")]
        execute_edit_hook("app.js", changes, str(tmp_path), str(project_dir), {})

        content = (project_dir / "app.js").read_text()
        assert content.count("// Header") == 1  # Não duplicou


class TestEditHookSearch:
    def test_insert_before(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("const app = express();\n")

        changes = [HookChange(
            search_string="const app",
            insert_before_value="const logger = require('logger');\n",
        )]
        execute_edit_hook("app.js", changes, str(tmp_path), str(project_dir), {})

        content = (project_dir / "app.js").read_text()
        assert "const logger" in content
        assert content.index("const logger") < content.index("const app")

    def test_insert_after(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("const app = express();\napp.listen(3000);\n")

        changes = [HookChange(
            search_string="const app = express();",
            insert_after_value="\nconst router = require('./router');",
        )]
        execute_edit_hook("app.js", changes, str(tmp_path), str(project_dir), {})

        content = (project_dir / "app.js").read_text()
        assert "const router" in content
        assert content.index("const app") < content.index("const router")

    def test_replace_by(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "config.js").write_text("const PORT = 3000;\n")

        changes = [HookChange(
            search_string="3000",
            replace_by_value="8080",
        )]
        execute_edit_hook("config.js", changes, str(tmp_path), str(project_dir), {})

        content = (project_dir / "config.js").read_text()
        assert "8080" in content
        assert "3000" not in content


class TestEditHookWithSnippet:
    def test_insert_snippet(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        (plugin_dir / "snippets").mkdir(parents=True)
        (plugin_dir / "snippets" / "footer.txt").write_text("// Footer de {{name}}\n")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("const app = express();\n")

        changes = [HookChange(insert_line=-1, insert_snippet="snippets/footer.txt")]
        execute_edit_hook("app.js", changes, str(plugin_dir), str(project_dir), {"name": "kafka"})

        content = (project_dir / "app.js").read_text()
        assert "Footer de kafka" in content

    def test_search_with_snippet_before(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        (plugin_dir / "snippets").mkdir(parents=True)
        (plugin_dir / "snippets" / "import.txt").write_text("const kafka = require('kafka');\n")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("const app = express();\n")

        changes = [HookChange(
            search_string="const app",
            insert_before_snippet="snippets/import.txt",
        )]
        execute_edit_hook("app.js", changes, str(plugin_dir), str(project_dir), {})

        content = (project_dir / "app.js").read_text()
        assert "const kafka" in content
        assert content.index("const kafka") < content.index("const app")


class TestEditHookGuards:
    def test_when_not_exists_prevents_duplicate(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("const kafka = require('kafka');\nconst app = express();\n")

        changes = [HookChange(
            search_string="const app",
            insert_before_value="const kafka = require('kafka');\n",
            when_not_exists="const kafka",
        )]
        execute_edit_hook("app.js", changes, str(tmp_path), str(project_dir), {})

        content = (project_dir / "app.js").read_text()
        assert content.count("const kafka") == 1  # Idempotente

    def test_when_exists_allows_operation(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("OLD_VALUE\n")

        changes = [HookChange(
            search_string="OLD_VALUE",
            replace_by_value="NEW_VALUE",
            when_exists="OLD_VALUE",
        )]
        execute_edit_hook("app.js", changes, str(tmp_path), str(project_dir), {})

        assert "NEW_VALUE" in (project_dir / "app.js").read_text()

    def test_when_exists_blocks_when_absent(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.js").write_text("SOMETHING\n")

        changes = [HookChange(
            search_string="SOMETHING",
            replace_by_value="REPLACED",
            when_exists="MISSING_GUARD",
        )]
        execute_edit_hook("app.js", changes, str(tmp_path), str(project_dir), {})

        assert "SOMETHING" in (project_dir / "app.js").read_text()


class TestEditHookJinjaPath:
    def test_path_with_jinja(self, tmp_path):
        project_dir = tmp_path / "project"
        (project_dir / "meu-app").mkdir(parents=True)
        (project_dir / "meu-app" / "config.js").write_text("PORT=3000\n")

        changes = [HookChange(search_string="3000", replace_by_value="8080")]
        execute_edit_hook(
            "{{name}}/config.js", changes, str(tmp_path),
            str(project_dir), {"name": "meu-app"},
        )

        assert "8080" in (project_dir / "meu-app" / "config.js").read_text()


# ═══════════════════════════════════════════════════════════════════════════════
# Step 10: run (hook)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunHook:
    def test_echo_command(self, tmp_path):
        exit_code = execute_run_hook(
            commands=["echo done"],
            project_dir=str(tmp_path),
            variables={},
        )
        assert exit_code == 0

    def test_jinja_in_command(self, tmp_path):
        exit_code = execute_run_hook(
            commands=["echo {{greeting}}"],
            project_dir=str(tmp_path),
            variables={"greeting": "hello"},
        )
        assert exit_code == 0

    def test_failing_command(self, tmp_path):
        exit_code = execute_run_hook(
            commands=["exit 1"],
            project_dir=str(tmp_path),
            variables={},
        )
        assert exit_code != 0

    def test_stops_on_first_failure(self, tmp_path):
        marker_file = tmp_path / "marker.txt"
        exit_code = execute_run_hook(
            commands=[
                "exit 1",
                f"echo ok > {marker_file}",
            ],
            project_dir=str(tmp_path),
            variables={},
        )
        assert exit_code != 0
        assert not marker_file.exists()
