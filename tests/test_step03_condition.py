"""Testes do Step 03 — Avaliador de Condições."""

from templi.core.condition_evaluator import evaluate_condition
from templi.core.models import Condition


# ═══════════════════════════════════════════════════════════════════════════════
# CA-03.1: Igualdade simples
# ═══════════════════════════════════════════════════════════════════════════════

class TestEqualOperator:
    def test_equal_true(self):
        condition = Condition(variable="ecosystem", operator="==", value="dotnet")
        assert evaluate_condition(condition, {"ecosystem": "dotnet"}) is True

    def test_equal_false(self):
        condition = Condition(variable="ecosystem", operator="==", value="dotnet")
        assert evaluate_condition(condition, {"ecosystem": "nodejs"}) is False


# ═══════════════════════════════════════════════════════════════════════════════
# CA-03.2: Diferença
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotEqualOperator:
    def test_not_equal_true(self):
        condition = Condition(variable="ecosystem", operator="!=", value="dotnet")
        assert evaluate_condition(condition, {"ecosystem": "nodejs"}) is True

    def test_not_equal_false(self):
        condition = Condition(variable="ecosystem", operator="!=", value="dotnet")
        assert evaluate_condition(condition, {"ecosystem": "dotnet"}) is False


# ═══════════════════════════════════════════════════════════════════════════════
# CA-03.3: ContainsAny com lista
# ═══════════════════════════════════════════════════════════════════════════════

class TestContainsAnyList:
    def test_list_intersection(self):
        condition = Condition(variable="app_types", operator="containsAny", value=["webapi"])
        assert evaluate_condition(condition, {"app_types": ["webapi", "worker"]}) is True

    def test_list_no_intersection(self):
        condition = Condition(variable="app_types", operator="containsAny", value=["job"])
        assert evaluate_condition(condition, {"app_types": ["webapi", "worker"]}) is False

    def test_list_multiple_expected(self):
        condition = Condition(variable="app_types", operator="containsAny", value=["job", "worker"])
        assert evaluate_condition(condition, {"app_types": ["webapi", "worker"]}) is True


# ═══════════════════════════════════════════════════════════════════════════════
# CA-03.4: ContainsAny com string (substring)
# ═══════════════════════════════════════════════════════════════════════════════

class TestContainsAnyString:
    def test_exact_match_in_list(self):
        condition = Condition(
            variable="scenario", operator="containsAny",
            value=["webapiProducer", "webapiAmbos"]
        )
        assert evaluate_condition(condition, {"scenario": "webapiProducer"}) is True

    def test_substring_match(self):
        condition = Condition(
            variable="plugin_applied", operator="containsAny", value=["onion"]
        )
        assert evaluate_condition(condition, {"plugin_applied": "plugin-onion-api"}) is True

    def test_no_match(self):
        condition = Condition(
            variable="scenario", operator="containsAny",
            value=["webapiProducer", "webapiAmbos"]
        )
        assert evaluate_condition(condition, {"scenario": "workerConsumer"}) is False

    def test_string_exact_match_in_list(self):
        condition = Condition(
            variable="catalog_application_type", operator="containsAny",
            value=["webapi", "worker"]
        )
        assert evaluate_condition(condition, {"catalog_application_type": "webapi"}) is True
        assert evaluate_condition(condition, {"catalog_application_type": "job"}) is False


# ═══════════════════════════════════════════════════════════════════════════════
# CA-03.5: NotContainsAny
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotContainsAny:
    def test_not_contains_true(self):
        condition = Condition(
            variable="plugin_applied", operator="notContainsAny", value=["onion"]
        )
        assert evaluate_condition(condition, {"plugin_applied": "plugin-kafka"}) is True

    def test_not_contains_false(self):
        condition = Condition(
            variable="plugin_applied", operator="notContainsAny", value=["onion"]
        )
        assert evaluate_condition(condition, {"plugin_applied": "plugin-onion"}) is False

    def test_not_contains_list(self):
        condition = Condition(
            variable="app_types", operator="notContainsAny", value=["webapi"]
        )
        assert evaluate_condition(condition, {"app_types": ["worker", "job"]}) is True
        assert evaluate_condition(condition, {"app_types": ["webapi", "job"]}) is False


# ═══════════════════════════════════════════════════════════════════════════════
# CA-03.6: Variável inexistente
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingVariable:
    def test_equal_missing_variable(self):
        condition = Condition(variable="missing_var", operator="==", value="dotnet")
        assert evaluate_condition(condition, {}) is False

    def test_contains_any_missing_variable(self):
        condition = Condition(variable="missing_var", operator="containsAny", value=["webapi"])
        assert evaluate_condition(condition, {}) is False


# ═══════════════════════════════════════════════════════════════════════════════
# CA-03.7: Sem condição (None)
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoCondition:
    def test_none_returns_true_empty_vars(self):
        assert evaluate_condition(None, {}) is True

    def test_none_returns_true_with_vars(self):
        assert evaluate_condition(None, {"x": "y"}) is True
