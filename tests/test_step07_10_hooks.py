"""Testes dos Steps 07-10 — Hook Executors."""

import os
import pytest

from templi.hooks.render_templates import execute_render_templates_hook
from templi.hooks.edit_file import execute_edit_hook
from templi.hooks.run_command import execute_run_hook
from templi.hooks.run_script import _build_environment, execute_run_script_hook
from templi.core.models import HookChange
from templi.core.runtime_config import COMPAT_NAME_ENV


class TestRunScriptEnvironment:
    def test_uses_default_templi_env_prefix(self, tmp_path, monkeypatch):
        monkeypatch.delenv(COMPAT_NAME_ENV, raising=False)

        plugin_dir = tmp_path / "plugin"
        project_dir = tmp_path / "project"

        env = _build_environment(
            str(plugin_dir),
            str(project_dir),
            {"debug": True},
        )

        assert env["TEMPLI_PLUGIN_DIR"] == os.path.abspath(str(plugin_dir))
        assert env["TEMPLI_PROJECT_DIR"] == os.path.abspath(str(project_dir))
        assert env["DEBUG"] == "true"

    def test_uses_compat_env_prefix(self, tmp_path, monkeypatch):
        monkeypatch.setenv(COMPAT_NAME_ENV, "CustomTool")
        monkeypatch.setenv("TEMPLI_PLUGIN_DIR", "stale-plugin")
        monkeypatch.setenv("TEMPLI_PROJECT_DIR", "stale-project")

        plugin_dir = tmp_path / "plugin"
        project_dir = tmp_path / "project"

        env = _build_environment(str(plugin_dir), str(project_dir), {})

        assert env["CUSTOMTOOL_PLUGIN_DIR"] == os.path.abspath(str(plugin_dir))
        assert env["CUSTOMTOOL_PROJECT_DIR"] == os.path.abspath(str(project_dir))
        assert "TEMPLI_PLUGIN_DIR" not in env
        assert "TEMPLI_PROJECT_DIR" not in env

    def test_metadata_mock_exposes_global_computed_inputs(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        script_file = scripts_dir / "uses_global_computed_inputs.py"
        script_file.write_text(
            "\n".join([
                "def run(metadata):",
                "    metadata.global_computed_inputs.pop('entrypoint', None)",
                "    metadata.global_computed_inputs['entrypoint'] = 'Sample.Api'",
            ]),
            encoding="utf-8",
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = execute_run_script_hook(
            script_path="./scripts/uses_global_computed_inputs.py",
            plugin_source_dir=str(plugin_dir),
            project_dir=str(project_dir),
            variables={},
            global_computed_inputs={"entrypoint": "OldValue"},
        )

        assert result.exit_code == 0
        assert result.global_computed_inputs["entrypoint"] == "Sample.Api"

    def test_metadata_mock_exposes_all_categories_and_all_inputs(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        script_file = scripts_dir / "reads_all.py"
        script_file.write_text(
            "\n".join([
                "import json, os",
                "def run(metadata):",
                "    snapshot = {",
                "        'inputs': dict(metadata.inputs),",
                "        'global_inputs': dict(metadata.global_inputs),",
                "        'computed_inputs': dict(metadata.computed_inputs),",
                "        'global_computed_inputs': dict(metadata.global_computed_inputs),",
                "        'all_inputs': metadata.all_inputs(),",
                "        'target_path': metadata.target_path,",
                "    }",
                "    out = os.path.join(metadata.target_path, 'snapshot.json')",
                "    with open(out, 'w', encoding='utf-8') as fh:",
                "        json.dump(snapshot, fh)",
            ]),
            encoding="utf-8",
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = execute_run_script_hook(
            script_path="./scripts/reads_all.py",
            plugin_source_dir=str(plugin_dir),
            project_dir=str(project_dir),
            variables={},
            inputs={"name": "kafka"},
            global_inputs={"solution_name": "Sample"},
            computed_inputs={"filename": "kafka"},
            global_computed_inputs={"plugin_applied": "-kafka"},
        )

        assert result.exit_code == 0

        import json as _json
        snapshot = _json.loads((project_dir / "snapshot.json").read_text(encoding="utf-8"))
        assert snapshot["inputs"] == {"name": "kafka"}
        assert snapshot["global_inputs"] == {"solution_name": "Sample"}
        assert snapshot["computed_inputs"] == {"filename": "kafka"}
        assert snapshot["global_computed_inputs"] == {"plugin_applied": "-kafka"}
        assert snapshot["all_inputs"] == {
            "name": "kafka",
            "solution_name": "Sample",
            "filename": "kafka",
            "plugin_applied": "-kafka",
        }
        assert snapshot["target_path"] == os.path.abspath(str(project_dir))

    def test_metadata_mutations_propagate_to_inputs_and_globals(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        script_file = scripts_dir / "mutates.py"
        script_file.write_text(
            "\n".join([
                "def run(metadata):",
                "    metadata.inputs['pathInfrastructure'] = 'src/Sample.Infrastructure'",
                "    metadata.global_inputs.pop('entrypoint', None)",
                "    metadata.global_computed_inputs.pop('entrypoint', None)",
                "    metadata.global_computed_inputs['entrypoint'] = 'Sample.Api'",
                "    metadata.global_computed_inputs['repositorypath'] = '/src/x.csproj'",
            ]),
            encoding="utf-8",
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = execute_run_script_hook(
            script_path="./scripts/mutates.py",
            plugin_source_dir=str(plugin_dir),
            project_dir=str(project_dir),
            variables={},
            inputs={"name": "kafka"},
            global_inputs={"entrypoint": "OldEntry"},
            global_computed_inputs={"entrypoint": "OldEntry"},
        )

        assert result.exit_code == 0
        assert result.inputs["pathInfrastructure"] == "src/Sample.Infrastructure"
        assert result.inputs["name"] == "kafka"
        assert "entrypoint" not in result.global_inputs
        assert result.global_computed_inputs["entrypoint"] == "Sample.Api"
        assert result.global_computed_inputs["repositorypath"] == "/src/x.csproj"

    def test_metadata_missing_script_returns_initial_state(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = execute_run_script_hook(
            script_path="./scripts/inexistente.py",
            plugin_source_dir=str(plugin_dir),
            project_dir=str(project_dir),
            variables={},
            inputs={"name": "kafka"},
            global_computed_inputs={"x": "y"},
        )

        assert result.exit_code == 1
        # Mesmo sem rodar, retorna o estado inicial dos dicts para o orchestrator.
        assert result.inputs == {"name": "kafka"}
        assert result.global_computed_inputs == {"x": "y"}


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
