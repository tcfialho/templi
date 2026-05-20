"""Teste de compatibilidade avançado (Regex, Jinja filters)."""

import re
from templi.core.template_engine import render_template_string
from templi.core.input_collector import _validate_input
from templi.core.models import PluginInput

class TestAdvancedCompatibility:

    def test_advanced_regex(self):
        """Valida regex com negative lookahead (usado no api-net8-empty)."""
        pattern = r"^(?!.*(?:\.[aA][pP][iI]|\.[jJ][oO][bB]|\.[wW][oO][rR][kK][eE][rR]))(?:[A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)*)$"
        
        # Casos válidos
        assert re.match(pattern, "Meu.Projeto")
        assert re.match(pattern, "MeuCarro.Vendas")
        
        # Casos inválidos (contém .Api, .Worker, .Job no meio ou fim)
        assert not re.match(pattern, "Meu.Projeto.Api")
        assert not re.match(pattern, "Meu.Projeto.Worker")
        assert not re.match(pattern, "Meu.Job.Teste")

    def test_input_validation_regex(self):
        """Valida que _validate_input usa re.match corretamente."""
        input_def = PluginInput(
            name="test",
            label="Test",
            type="text",
            pattern=r"^[A-Z][a-z]+$"
        )
        
        # Válido
        _validate_input(input_def, "Word")
        
        # Inválido
        try:
            _validate_input(input_def, "word")
            assert False, "Deveria falhar"
        except ValueError:
            pass

    def test_jinja_filters_builtin(self):
        """Valida filtros Jinja padrão (join, replace, lower, upper)."""
        # join
        assert render_template_string("{{ x | join(', ') }}", {"x": ["a", "b"]}) == "a, b"
        
        # replace
        assert render_template_string("{{ x | replace('-', '') }}", {"x": "a-b-c"}) == "abc"
        
        # upper/lower
        assert render_template_string("{{ x | upper }}", {"x": "abc"}) == "ABC"
        assert render_template_string("{{ x | lower }}", {"x": "ABC"}) == "abc"
        
    def test_jinja_filters_custom(self):
        """Valida filtros customizados (kebabcase, pascalcase)."""
        assert render_template_string("{{ x | kebabcase }}", {"x": "MeuProjeto"}) == "meu-projeto"
        assert render_template_string("{{ x | pascalcase }}", {"x": "meu-projeto"}) == "MeuProjeto"

