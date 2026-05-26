"""Testes de lacunas encontradas na análise de compatibilidade."""

import os
import pytest
import yaml

from templi.core.plugin_loader import load_plugin
from templi.core.condition_evaluator import evaluate_condition
from templi.core.models import Condition, HookChange
from templi.core.template_engine import create_jinja_env, render_template_string
from templi.hooks.edit_file import execute_edit_hook

REAL_PLUGINS_BASE = r"C:\Users\Admin\Documents\plugin-fixtures"


# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA 1: insert line: -2, -3 (linhas negativas genéricas)
# ═══════════════════════════════════════════════════════════════════════════════

class TestInsertNegativeLines:
    """Testa inserção em linhas negativas contando do final."""

    def test_insert_line_minus_2(self, tmp_path):
        """line: -2 = antes da penúltima linha (contando linhas em branco)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "file.cs").write_text(
            "linha1\nlinha2\nlinha3\nlinha4\n"
        )

        changes = [HookChange(insert_line=-2, insert_value="INSERIDO\n")]
        execute_edit_hook("file.cs", changes, str(tmp_path), str(project_dir), {})

        lines = (project_dir / "file.cs").read_text().splitlines()
        assert len(lines) == 5
        assert lines[2] == "INSERIDO"
        assert lines[3] == "linha3"
        assert lines[4] == "linha4"

    def test_insert_line_minus_2_with_guard(self, tmp_path):
        """line: -2 com when.not-exists deve ser idempotente."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        content = "using System;\nnamespace Foo {\n    // corpo\n}\n"
        (project_dir / "file.cs").write_text(content)

        changes = [HookChange(
            insert_line=-2,
            insert_value="    Task Inserir();\n",
            when_not_exists="Task Inserir",
        )]
        execute_edit_hook("file.cs", changes, str(tmp_path), str(project_dir), {})

        result = (project_dir / "file.cs").read_text()
        assert "Task Inserir();" in result

        # Aplicar de novo — não deve duplicar
        execute_edit_hook("file.cs", changes, str(tmp_path), str(project_dir), {})
        result2 = (project_dir / "file.cs").read_text()
        assert result2.count("Task Inserir") == 1

    def test_insert_line_minus_3(self, tmp_path):
        """line: -3 = inserir 3 linhas antes do final (antes de C em ABCDE)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "file.txt").write_text(
            "A\nB\nC\nD\nE\n"
        )

        changes = [HookChange(insert_line=-3, insert_value="X\n")]
        execute_edit_hook("file.txt", changes, str(tmp_path), str(project_dir), {})

        lines = (project_dir / "file.txt").read_text().splitlines()
        assert "X" in lines
        # -3 com 5 linhas: target_index = max(5 + (-3), 0) = 2 (antes da 3ª linha, C)
        x_index = lines.index("X")
        c_index = lines.index("C")
        assert x_index == c_index - 1

    def test_insert_line_minus_1_blank_section_after_trailing_newline(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "README.md").write_text(
            "Existing paragraph.\n",
            encoding="utf-8",
        )

        changes = [HookChange(insert_line=-1, insert_value="\n## Section\n")]
        execute_edit_hook("README.md", changes, str(tmp_path), str(project_dir), {})

        assert (project_dir / "README.md").read_text() == (
            "Existing paragraph.\n\n## Section\n"
        )

    def test_insert_line_minus_1_no_blank_when_content_has_no_trailing_newline(
        self, tmp_path,
    ):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "setup.ts").write_text("import 'jest-dom';", encoding="utf-8")

        changes = [HookChange(insert_line=-1, insert_value="\nimport { server } from './server';\n")]
        execute_edit_hook("setup.ts", changes, str(tmp_path), str(project_dir), {})

        assert (project_dir / "setup.ts").read_text() == (
            "import 'jest-dom';\nimport { server } from './server';\n"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA 2: replace-by: snippet (além de replace-by: value)
# ═══════════════════════════════════════════════════════════════════════════════

class TestReplaceBySnippet:
    """Testa replace-by com snippet (arquivo externo)."""

    def test_replace_by_snippet(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        (plugin_dir / "snippets").mkdir(parents=True)
        (plugin_dir / "snippets" / "constructor.txt").write_text(
            "public Controller(ILogger logger, IService service)"
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "Controller.cs").write_text(
            "public Controller(ILogger logger)"
        )

        changes = [HookChange(
            search_string="public Controller(ILogger logger)",
            replace_by_snippet="snippets/constructor.txt",
        )]
        execute_edit_hook(
            "Controller.cs", changes, str(plugin_dir), str(project_dir), {},
        )

        content = (project_dir / "Controller.cs").read_text()
        assert "IService service" in content
        assert "public Controller(ILogger logger)" not in content

    def test_replace_by_snippet_with_jinja(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        (plugin_dir / "snippets").mkdir(parents=True)
        (plugin_dir / "snippets" / "constructor.txt").write_text(
            "public {{classname}}Controller(ILogger logger, IService svc)"
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "Controller.cs").write_text(
            "public OLD_CONSTRUCTOR"
        )

        changes = [HookChange(
            search_string="public OLD_CONSTRUCTOR",
            replace_by_snippet="snippets/constructor.txt",
        )]
        execute_edit_hook(
            "Controller.cs", changes, str(plugin_dir),
            str(project_dir), {"classname": "Veiculo"},
        )

        content = (project_dir / "Controller.cs").read_text()
        assert "VeiculoController" in content


# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA 3: encoding em hooks edit (deve parsear sem crash)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEncodingInEditHook:
    """encoding é parseado no Hook mas não muda funcionalidade."""

    PLUGIN_DIR = os.path.join(REAL_PLUGINS_BASE, "dotnet", "plugin-correlation-id")

    @pytest.fixture(autouse=True)
    def skip_if_not_available(self):
        if not os.path.isdir(self.PLUGIN_DIR):
            pytest.skip("plugin-correlation-id não disponível")

    def test_encoding_parsed(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        edit_hooks_with_encoding = [
            hook for hook in plugin.spec.hooks
            if hook.type == "edit" and hook.encoding is not None
        ]
        assert len(edit_hooks_with_encoding) >= 1
        assert edit_hooks_with_encoding[0].encoding == "utf-8"


# ═══════════════════════════════════════════════════════════════════════════════
# Compatibilidade: Guards de insert com variáveis Jinja
# (ex: when.not-exists: '{{solution_name}}.Infrastructure')
# ═══════════════════════════════════════════════════════════════════════════════

class TestGuardsWithJinja:
    def test_insert_guard_with_jinja_variable(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "Program.cs").write_text(
            "using System;\n"
        )

        changes = [HookChange(
            insert_line=0,
            insert_value="using MeuProjeto.Infrastructure;\n",
            when_not_exists="{{solution_name}}.Infrastructure",
        )]
        execute_edit_hook(
            "Program.cs", changes, str(tmp_path),
            str(project_dir), {"solution_name": "MeuProjeto"},
        )

        content = (project_dir / "Program.cs").read_text()
        assert "MeuProjeto.Infrastructure" in content

    def test_insert_guard_jinja_blocks_when_exists(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "Program.cs").write_text(
            "using MeuProjeto.Infrastructure;\nusing System;\n"
        )

        changes = [HookChange(
            insert_line=0,
            insert_value="using MeuProjeto.Infrastructure;\n",
            when_not_exists="{{solution_name}}.Infrastructure",
        )]
        execute_edit_hook(
            "Program.cs", changes, str(tmp_path),
            str(project_dir), {"solution_name": "MeuProjeto"},
        )

        content = (project_dir / "Program.cs").read_text()
        assert content.count("MeuProjeto.Infrastructure") == 1  # Idempotente


# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA 4: Loader carrega plugin-onion (plugin complexo com -2)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadOnionPlugin:
    PLUGIN_DIR = os.path.join(REAL_PLUGINS_BASE, "dotnet", "plugin-onion")

    @pytest.fixture(autouse=True)
    def skip_if_not_available(self):
        if not os.path.isdir(self.PLUGIN_DIR):
            pytest.skip("plugin-onion não disponível")

    def test_loads_all_hooks(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert len(plugin.spec.hooks) > 20

    def test_has_minus_2_inserts(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        minus_2_changes = []
        for hook in plugin.spec.hooks:
            if hook.changes:
                for change in hook.changes:
                    if change.insert_line is not None and change.insert_line < -1:
                        minus_2_changes.append(change)
        assert len(minus_2_changes) >= 1

    def test_multiselect_operations(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        operations_input = None
        for inp in plugin.spec.inputs:
            if inp.name == "operations":
                operations_input = inp
                break
        assert operations_input is not None
        assert operations_input.type == "multiselect"
        assert len(operations_input.items) >= 5

    def test_v2_schema(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        assert plugin.schema_version == "v2"


# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA: Loader carrega plugin-correlation-id (com encoding + replace-by snippet)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadCorrelationIdPlugin:
    PLUGIN_DIR = os.path.join(REAL_PLUGINS_BASE, "dotnet", "plugin-correlation-id")

    @pytest.fixture(autouse=True)
    def skip_if_not_available(self):
        if not os.path.isdir(self.PLUGIN_DIR):
            pytest.skip("plugin-correlation-id não disponível")

    def test_has_replace_by_snippet(self):
        plugin = load_plugin(self.PLUGIN_DIR)
        snippet_replaces = []
        for hook in plugin.spec.hooks:
            if hook.changes:
                for change in hook.changes:
                    if change.replace_by_snippet:
                        snippet_replaces.append(change)
        assert len(snippet_replaces) >= 1
        assert "snippets/" in snippet_replaces[0].replace_by_snippet

    def test_docs_field_parsed(self):
        """spec.docs é campo inerte mas não deve causar crash."""
        plugin = load_plugin(self.PLUGIN_DIR)
        assert plugin.metadata.name == "plugin-correlation-id"


# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA 5: search.pattern em hooks edit (busca por regex)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchPattern:
    """Testa search.pattern (regex) em hooks edit."""

    def test_search_pattern_replace_by_value(self, tmp_path):
        """search.pattern com replace-by: value usando regex."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.csproj").write_text(
            '<PackageReference Include="BuildingBlock.Crypto" Version="1.0.0" />\n'
        )

        changes = [HookChange(
            search_pattern='Include="BuildingBlock.Crypto" Version=".*?"',
            replace_by_value='Include="BuildingBlock.Crypto" Version="2.1.0"',
        )]
        execute_edit_hook(
            "app.csproj", changes, str(tmp_path), str(project_dir), {},
        )

        content = (project_dir / "app.csproj").read_text()
        assert 'Version="2.1.0"' in content
        assert 'Version="1.0.0"' not in content

    def test_search_pattern_literal_string(self, tmp_path):
        """search.pattern com string literal (sem metacaracteres regex)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "README.md").write_text(
            "# Docs\nAcessar a url: http://localhost\n"
        )

        changes = [HookChange(
            search_pattern="Acessar a url:",
            replace_by_value="Acessar a url (Swagger):",
        )]
        execute_edit_hook(
            "README.md", changes, str(tmp_path), str(project_dir), {},
        )

        content = (project_dir / "README.md").read_text()
        assert "Acessar a url (Swagger):" in content
        assert content.count("Acessar a url:") == 0  # original substituído

    def test_search_pattern_with_when_not_exists(self, tmp_path):
        """search.pattern com guard when.not-exists."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "file.cs").write_text(
            "AddHttpClient<IService, ServiceImpl>()\nWithHandler\n"
        )

        changes = [HookChange(
            search_pattern="AddHttpClient<IService, ServiceImpl>\\(\\)",
            replace_by_value="AddHttpClient<IService, ServiceImpl>()\n    .WithCryptoHandler",
            when_not_exists="WithCryptoHandler",
        )]

        # Primeira aplicação
        execute_edit_hook(
            "file.cs", changes, str(tmp_path), str(project_dir), {},
        )
        content = (project_dir / "file.cs").read_text()
        assert "WithCryptoHandler" in content

        # Segunda aplicação — idempotente por causa do guard
        execute_edit_hook(
            "file.cs", changes, str(tmp_path), str(project_dir), {},
        )
        content2 = (project_dir / "file.cs").read_text()
        assert content2.count("WithCryptoHandler") == content.count("WithCryptoHandler")

    def test_search_pattern_insert_before(self, tmp_path):
        """search.pattern com insert-before."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "file.txt").write_text("AAA\nBBB\nCCC\n")

        changes = [HookChange(
            search_pattern="B+",
            insert_before_value="BEFORE\n",
        )]
        execute_edit_hook(
            "file.txt", changes, str(tmp_path), str(project_dir), {},
        )

        content = (project_dir / "file.txt").read_text()
        assert "BEFORE\nBBB" in content

    def test_search_pattern_insert_after(self, tmp_path):
        """search.pattern com insert-after (line-level: insere após a LINHA)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "file.txt").write_text("AAA\nBBB\nCCC\n")

        changes = [HookChange(
            search_pattern="B+",
            insert_after_value="AFTER\n",
        )]
        execute_edit_hook(
            "file.txt", changes, str(tmp_path), str(project_dir), {},
        )

        content = (project_dir / "file.txt").read_text()
        assert "BBB\nAFTER\n" in content
        assert content == "AAA\nBBB\nAFTER\nCCC\n"

    def test_search_pattern_no_match(self, tmp_path):
        """search.pattern que não encontra match não altera o arquivo."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        original = "conteudo original\n"
        (project_dir / "file.txt").write_text(original)

        changes = [HookChange(
            search_pattern="INEXISTENTE_\\d+",
            replace_by_value="replacement",
        )]
        execute_edit_hook(
            "file.txt", changes, str(tmp_path), str(project_dir), {},
        )

        assert (project_dir / "file.txt").read_text() == original


class TestSearchPatternRealPlugins:
    """Testa que plugins reais com search.pattern são parseados corretamente."""

    CRYPTO_PLUGIN_DIR = os.path.join(
        REAL_PLUGINS_BASE, "dotnet", "plugin-http-cryptography"
    )

    @pytest.fixture(autouse=True)
    def skip_if_not_available(self):
        if not os.path.isdir(self.CRYPTO_PLUGIN_DIR):
            pytest.skip("plugin-http-cryptography não disponível")

    def test_crypto_plugin_has_search_pattern(self):
        """http-cryptography usa search.pattern para regex de versão NuGet."""
        plugin = load_plugin(self.CRYPTO_PLUGIN_DIR)
        pattern_changes = []
        for hook in plugin.spec.hooks:
            if hook.changes:
                for change in hook.changes:
                    if change.search_pattern:
                        pattern_changes.append(change)
        assert len(pattern_changes) >= 2
        assert ".*?" in pattern_changes[0].search_pattern


# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA 6: Booleanos YAML em condições (value: true/false sem aspas)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBooleanConditionValues:
    """Testa que condições com valores booleanos YAML funcionam corretamente."""

    def test_yaml_false_matches_string_false(self):
        """YAML `value: false` (bool False) deve casar com string 'false'."""
        condition = Condition(variable="flag", operator="==", value=False)
        assert evaluate_condition(condition, {"flag": "false"})

    def test_yaml_true_matches_string_true(self):
        """YAML `value: true` (bool True) deve casar com string 'true'."""
        condition = Condition(variable="flag", operator="==", value=True)
        assert evaluate_condition(condition, {"flag": "true"})

    def test_yaml_bool_matches_python_bool(self):
        """YAML bool True deve casar com Python bool True."""
        condition = Condition(variable="flag", operator="==", value=True)
        assert evaluate_condition(condition, {"flag": True})

    def test_yaml_false_not_matches_string_true(self):
        """YAML `value: false` NÃO deve casar com string 'true'."""
        condition = Condition(variable="flag", operator="==", value=False)
        assert not evaluate_condition(condition, {"flag": "true"})

    def test_string_True_matches_yaml_true(self):
        """String 'True' (capitalizada) deve casar com YAML true."""
        condition = Condition(variable="flag", operator="==", value=True)
        assert evaluate_condition(condition, {"flag": "True"})

    def test_string_False_matches_yaml_false(self):
        """String 'False' (capitalizada) deve casar com YAML false."""
        condition = Condition(variable="flag", operator="==", value=False)
        assert evaluate_condition(condition, {"flag": "False"})

    def test_not_equal_bool(self):
        """Operador != com booleanos."""
        condition = Condition(variable="flag", operator="!=", value=False)
        assert evaluate_condition(condition, {"flag": "true"})
        assert not evaluate_condition(condition, {"flag": "false"})

    def test_regular_string_equality_preserved(self):
        """Strings regulares (não-booleanas) preservam comparação normal."""
        condition = Condition(variable="name", operator="==", value="hello")
        assert evaluate_condition(condition, {"name": "hello"})
        assert not evaluate_condition(condition, {"name": "Hello"})

    def test_gmud_scenario(self):
        """Cenário real: select retorna 'false' e condition tem value: false (YAML bool)."""
        # Simula o cenário do plugin-gmud:
        # input select com default "true", user selects "false"
        # condition: variable: u_used_appdynamics_or_sonar, operator: ==, value: false
        condition = Condition(
            variable="u_used_appdynamics_or_sonar",
            operator="==",
            value=False,  # YAML parseia false unquoted como bool
        )
        variables = {"u_used_appdynamics_or_sonar": "false"}  # select retorna string
        assert evaluate_condition(condition, variables)


# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA 7: global_inputs namespace em computed-inputs Jinja
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA 8: when como sibling de insert (ao invés de aninhado)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhenAsSibling:
    """Testa que when funciona como sibling de insert/search."""

    def test_when_sibling_of_insert_parsed(self):
        """YAML: when como sibling de insert deve ser parseado."""
        import yaml
        from templi.core.plugin_loader import _parse_change

        raw_yaml = """
insert:
  line: -1
  snippet: snippets/readme.txt
when:
  not-exists: "# Header"
"""
        raw = yaml.safe_load(raw_yaml)
        change = _parse_change(raw)
        assert change.insert_line == -1
        assert change.insert_snippet == "snippets/readme.txt"
        assert change.when_not_exists == "# Header"

    def test_when_sibling_of_insert_blocks_duplicate(self, tmp_path):
        """when sibling deve bloquear duplicacao igual ao aninhado."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "README.md").write_text("# Doc\nContent\n", encoding="utf-8")

        changes = [HookChange(
            insert_line=-1,
            insert_snippet=None,
            insert_value="# Mutation Tests\n",
            when_not_exists="# Mutation Tests",
        )]
        execute_edit_hook("README.md", changes, str(tmp_path), str(project_dir), {})

        content = (project_dir / "README.md").read_text(encoding="utf-8")
        assert "# Mutation Tests" in content

        # Segunda aplicacao - idempotente
        execute_edit_hook("README.md", changes, str(tmp_path), str(project_dir), {})
        content2 = (project_dir / "README.md").read_text(encoding="utf-8")
        assert content2.count("# Mutation Tests") == 1

    def test_when_nested_still_works(self):
        """when aninhado dentro de insert continua funcionando."""
        import yaml
        from templi.core.plugin_loader import _parse_change

        raw_yaml = """
insert:
  line: 0
  value: "using Foo;\\n"
  when:
    not-exists: "using Foo;"
"""
        raw = yaml.safe_load(raw_yaml)
        change = _parse_change(raw)
        assert change.when_not_exists == "using Foo;"


class TestGlobalInputsNamespace:
    """Testa que global_inputs é acessível como namespace em Jinja."""

    def test_global_inputs_dict_lookup(self):
        """Cenário real do plugin-helm: dict lookup via global_inputs."""
        from templi.core.computed_resolver import resolve_computed_inputs

        variables = {
            "helm": "netcore30-web",
            "global_inputs": {"helm": "netcore30-web"},
        }
        global_computed = {
            "helm_version": '{{ { "batchjob": "1.6", "netcore30-web": "2.8" }[global_inputs.helm] }}',
        }
        result = resolve_computed_inputs(
            computed_inputs={},
            global_computed_inputs=global_computed,
            variables=variables,
        )
        assert result["helm_version"] == "2.8"

    def test_global_inputs_simple_access(self):
        """Acesso simples a global_inputs.nome."""
        from templi.core.computed_resolver import resolve_computed_inputs

        variables = {
            "project_name": "my-project",
            "global_inputs": {"project_name": "my-project"},
        }
        computed = {
            "full_name": "app-{{ global_inputs.project_name }}",
        }
        result = resolve_computed_inputs(
            computed_inputs=computed,
            global_computed_inputs={},
            variables=variables,
        )
        assert result["full_name"] == "app-my-project"


class TestBooleanConditionRealPlugins:
    """Testa que plugins reais com condições booleanas são avaliados corretamente."""

    GMUD_PLUGIN_DIR = os.path.join(
        REAL_PLUGINS_BASE, "dotnet", "plugin-gmud"
    )

    @pytest.fixture(autouse=True)
    def skip_if_not_available(self):
        if not os.path.isdir(self.GMUD_PLUGIN_DIR):
            pytest.skip("plugin-gmud não disponível")

    def test_gmud_condition_with_bool_value(self):
        """plugin-gmud usa `value: false` em condição de input."""
        plugin = load_plugin(self.GMUD_PLUGIN_DIR)

        # Encontra o input com condição sobre u_used_appdynamics_or_sonar
        cond_input = None
        for inp in plugin.spec.inputs:
            if inp.condition and inp.condition.variable == "u_used_appdynamics_or_sonar":
                cond_input = inp
                break

        assert cond_input is not None
        # O valor veio do YAML como bool False — a condição deve funcionar
        condition = cond_input.condition
        variables = {"u_used_appdynamics_or_sonar": "false"}
        assert evaluate_condition(condition, variables)


# ═══════════════════════════════════════════════════════════════════════════════
# LACUNA 9: condition como campo em changes de hook edit (change-level condition)
# ═══════════════════════════════════════════════════════════════════════════════

class TestChangeLevelCondition:
    """Testa condition dentro de uma change de hook edit."""

    def test_change_condition_satisfied_applies(self, tmp_path):
        """Change com condition satisfeita deve ser aplicada."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "index.js").write_text(
            "async function startTasks() {\n}\n"
        )

        changes = [HookChange(
            search_string="async function startTasks()",
            insert_after_value="\n\tawait channel.publish({id: '123'});\n",
            when_not_exists="channel.publish",
            condition=Condition(
                variable="rabbitusecase",
                operator="containsAny",
                value=["Producer", "Ambos"],
            ),
        )]
        execute_edit_hook(
            "index.js", changes, str(tmp_path),
            str(project_dir), {"rabbitusecase": "Producer"},
        )

        content = (project_dir / "index.js").read_text()
        assert "channel.publish" in content

    def test_change_condition_not_satisfied_skips(self, tmp_path):
        """Change com condition NAO satisfeita deve ser pulada."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        original = "async function startTasks() {\n}\n"
        (project_dir / "index.js").write_text(original)

        changes = [HookChange(
            search_string="async function startTasks()",
            insert_after_value="\n\tawait channel.publish({id: '123'});\n",
            condition=Condition(
                variable="rabbitusecase",
                operator="containsAny",
                value=["Producer", "Ambos"],
            ),
        )]
        execute_edit_hook(
            "index.js", changes, str(tmp_path),
            str(project_dir), {"rabbitusecase": "Consumer"},
        )

        content = (project_dir / "index.js").read_text()
        assert content == original
        assert "channel.publish" not in content

    def test_change_without_condition_always_applies(self, tmp_path):
        """Change sem condition deve sempre ser aplicada (regressao)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "file.txt").write_text("line1\nline2\n")

        changes = [HookChange(
            search_string="line1",
            insert_after_value="\nINSERTED\n",
        )]
        execute_edit_hook(
            "file.txt", changes, str(tmp_path),
            str(project_dir), {},
        )

        content = (project_dir / "file.txt").read_text()
        assert "INSERTED" in content

    def test_change_condition_with_insert_line(self, tmp_path):
        """Change-level condition com insert por linha."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "file.txt").write_text("header\nbody\nfooter\n")

        changes = [HookChange(
            insert_line=0,
            insert_value="PREPEND\n",
            condition=Condition(
                variable="flag",
                operator="==",
                value="yes",
            ),
        )]

        # Condition met
        execute_edit_hook(
            "file.txt", changes, str(tmp_path),
            str(project_dir), {"flag": "yes"},
        )
        content = (project_dir / "file.txt").read_text()
        assert content.startswith("PREPEND\n")

    def test_change_condition_with_insert_line_skipped(self, tmp_path):
        """Change-level condition NAO satisfeita com insert por linha."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        original = "header\nbody\nfooter\n"
        (project_dir / "file.txt").write_text(original)

        changes = [HookChange(
            insert_line=0,
            insert_value="PREPEND\n",
            condition=Condition(
                variable="flag",
                operator="==",
                value="yes",
            ),
        )]

        # Condition NOT met
        execute_edit_hook(
            "file.txt", changes, str(tmp_path),
            str(project_dir), {"flag": "no"},
        )
        content = (project_dir / "file.txt").read_text()
        assert content == original

    def test_change_condition_parsed_from_yaml(self):
        """Parser extrai condition de dentro do bloco search."""
        from templi.core.plugin_loader import _parse_change

        raw_yaml = """
search:
  string: "async function startTasks()"
  condition:
    variable: rabbitusecase
    operator: containsAny
    value:
    - Producer
    - Ambos
  insert-after:
    value: "await publish();"
  when:
    not-exists: "await publish();"
"""
        raw = yaml.safe_load(raw_yaml)
        change = _parse_change(raw)

        assert change.search_string == "async function startTasks()"
        assert change.insert_after_value == "await publish();"
        assert change.when_not_exists == "await publish();"
        assert change.condition is not None
        assert change.condition.variable == "rabbitusecase"
        assert change.condition.operator == "containsAny"
        assert change.condition.value == ["Producer", "Ambos"]


class TestChangeLevelConditionRealPlugins:
    """Testa que plugins reais com change-level condition sao parseados."""

    RABBITMQ_PLUGIN_DIR = os.path.join(
        REAL_PLUGINS_BASE, "nodejs", "plugin-rabbitmq-nodejs"
    )

    @pytest.fixture(autouse=True)
    def skip_if_not_available(self):
        if not os.path.isdir(self.RABBITMQ_PLUGIN_DIR):
            pytest.skip("plugin-rabbitmq-nodejs nao disponivel")

    def test_rabbitmq_has_change_level_condition(self):
        """plugin-rabbitmq-nodejs usa condition dentro de search."""
        plugin = load_plugin(self.RABBITMQ_PLUGIN_DIR)

        changes_with_condition = []
        for hook in plugin.spec.hooks:
            if hook.changes:
                for change in hook.changes:
                    if change.condition is not None:
                        changes_with_condition.append(change)

        assert len(changes_with_condition) >= 1
        cond = changes_with_condition[0].condition
        assert cond.variable == "rabbitusecase"
        assert cond.operator == "containsAny"


# ═══════════════════════════════════════════════════════════════════════════════
# GAP #6 (E2E): Jinja2 trim_blocks / lstrip_blocks
# ═══════════════════════════════════════════════════════════════════════════════

class TestJinjaTrimBlocks:
    """Testa que o Jinja2 environment faz trim de block tags."""

    def test_trim_blocks_removes_blank_lines(self):
        """{% if %} nao deve gerar linhas em branco extras."""
        env = create_jinja_env()
        template = "line1\n{% if show %}shown\n{% endif %}line3\n"
        result = env.from_string(template).render({"show": True})
        assert result == "line1\nshown\nline3\n"

    def test_trim_blocks_false_branch(self):
        """Bloco nao satisfeito nao deve deixar linhas em branco."""
        env = create_jinja_env()
        template = "line1\n{% if show %}shown\n{% endif %}line3\n"
        result = env.from_string(template).render({"show": False})
        assert result == "line1\nline3\n"

    def test_lstrip_blocks_indented(self):
        """Block tags com indentacao devem ser removidos limpos."""
        env = create_jinja_env()
        template = "data:\n  {% if x %}value: yes\n  {% endif %}end\n"
        result = env.from_string(template).render({"x": True})
        assert result == "data:\nvalue: yes\nend\n"

    def test_catalog_info_like_template(self):
        """Simula padrao do catalog-info.yaml com {% if %}."""
        env = create_jinja_env()
        template = (
            "metadata:\n"
            "  name: {{name}}\n"
            "  {% if desc %}\n"
            "  description: {{desc}}\n"
            "  {% endif %}\n"
            "  owner: {{owner}}\n"
        )
        result = env.from_string(template).render({
            "name": "app", "desc": "My app", "owner": "team"
        })
        assert "  \n" not in result  # no blank indented lines
        assert "description: My app" in result
        assert "owner: team" in result


# ═══════════════════════════════════════════════════════════════════════════════
# GAP #7 (E2E): Leading slash in edit hook path
# ═══════════════════════════════════════════════════════════════════════════════

class TestEditHookLeadingSlash:
    """Testa que paths com / no inicio sao resolvidos relativamente ao projeto."""

    def test_leading_slash_stripped(self, tmp_path):
        """Path /file.txt deve criar arquivo dentro do projeto, nao na raiz."""
        target = tmp_path / "file.txt"
        target.write_text("original")

        changes = [HookChange(insert_line=-1, insert_value="\nnew content")]
        execute_edit_hook(
            hook_path="/file.txt",
            changes=changes,
            plugin_source_dir=str(tmp_path),
            project_dir=str(tmp_path),
            variables={},
        )
        result = target.read_text()
        assert "new content" in result

    def test_no_slash_still_works(self, tmp_path):
        """Path sem / inicial continua funcionando normalmente."""
        target = tmp_path / "data.txt"
        target.write_text("line1")

        changes = [HookChange(insert_line=-1, insert_value="\nline2")]
        execute_edit_hook(
            hook_path="data.txt",
            changes=changes,
            plugin_source_dir=str(tmp_path),
            project_dir=str(tmp_path),
            variables={},
        )
        result = target.read_text()
        assert "line2" in result

    def test_subdir_with_leading_slash(self, tmp_path):
        """Path /src/index.js com / inicial resolve no projeto."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        target = src_dir / "index.js"
        target.write_text("// code")

        changes = [HookChange(insert_line=-1, insert_value="\n// appended")]
        execute_edit_hook(
            hook_path="/src/index.js",
            changes=changes,
            plugin_source_dir=str(tmp_path),
            project_dir=str(tmp_path),
            variables={},
        )
        result = target.read_text()
        assert "// appended" in result
