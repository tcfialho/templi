"""Testes do Step 05 — Resolver de Computed Inputs."""

from templi.core.computed_resolver import resolve_computed_inputs


class TestStaticComputed:
    def test_static_value(self):
        result = resolve_computed_inputs(
            computed_inputs={"secret_name": "my-secret"},
            global_computed_inputs={},
            variables={},
        )
        assert result["secret_name"] == "my-secret"


class TestJinjaComputed:
    def test_template(self):
        result = resolve_computed_inputs(
            computed_inputs={"full_name": "plugin-{{plugin_name}}"},
            global_computed_inputs={},
            variables={"plugin_name": "kafka"},
        )
        assert result["full_name"] == "plugin-kafka"

    def test_filter_lower(self):
        result = resolve_computed_inputs(
            computed_inputs={"filename": "{{classname|lower}}"},
            global_computed_inputs={},
            variables={"classname": "MeuExemplo"},
        )
        assert result["filename"] == "meuexemplo"

    def test_replace_filter(self):
        result = resolve_computed_inputs(
            computed_inputs={},
            global_computed_inputs={"plugin_applied": "{{plugin_applied|replace('-kafka', '')}}-kafka"},
            variables={"plugin_applied": ""},
        )
        assert result["plugin_applied"] == "-kafka"


class TestConcatComputed:
    def test_concat(self):
        result = resolve_computed_inputs(
            computed_inputs={"scenario": "{{catalog_application_type}}{{kafkausecase}}"},
            global_computed_inputs={},
            variables={"catalog_application_type": "webapi", "kafkausecase": "Producer"},
        )
        assert result["scenario"] == "webapiProducer"


class TestChainedComputed:
    def test_chained(self):
        result = resolve_computed_inputs(
            computed_inputs={
                "prefix": "plugin",
                "full_name": "{{prefix}}-{{name}}",
            },
            global_computed_inputs={},
            variables={"name": "kafka"},
        )
        assert result["full_name"] == "plugin-kafka"


class TestUndefinedVariable:
    def test_undefined_returns_empty(self):
        result = resolve_computed_inputs(
            computed_inputs={"test": "{{variavel_inexistente}}"},
            global_computed_inputs={},
            variables={},
        )
        assert result["test"] == ""


class TestPluginAppliedInit:
    def test_plugin_applied_initialized(self):
        result = resolve_computed_inputs(
            computed_inputs={},
            global_computed_inputs={},
            variables={},
        )
        assert result["plugin_applied"] == ""


class TestRealPluginGeneratorComputed:
    def test_full_plugin_name(self):
        result = resolve_computed_inputs(
            computed_inputs={"full_plugin_name": "plugin-{{plugin_name}}"},
            global_computed_inputs={},
            variables={"plugin_name": "teste-kafka"},
        )
        assert result["full_plugin_name"] == "plugin-teste-kafka"


class TestRealKafkaComputed:
    def test_kafka_scenario(self):
        result = resolve_computed_inputs(
            computed_inputs={
                "scenario": "{{catalog_application_type}}{{kafkausecase}}",
                "filename": "{{classname_kafka|lower}}",
            },
            global_computed_inputs={
                "plugin_applied": "{{plugin_applied|replace('-kafka', '')}}-kafka",
            },
            variables={
                "catalog_application_type": "webapi",
                "kafkausecase": "Ambos",
                "classname_kafka": "Exemplo",
                "plugin_applied": "",
            },
        )
        assert result["scenario"] == "webapiAmbos"
        assert result["filename"] == "exemplo"
        assert result["plugin_applied"] == "-kafka"
