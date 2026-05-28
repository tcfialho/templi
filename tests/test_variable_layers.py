"""Testes de reconciliação genérica de camadas de variáveis."""

from templi.core.variable_layers import (
    incoming_extends_inherited,
    prefer_collected_global_value,
    reconcile_with_inherited_computed,
)


class TestIncomingExtendsInherited:
    def test_sln_suffix(self):
        assert incoming_extends_inherited("Acme.App", "Acme.App.sln")

    def test_same_value(self):
        assert not incoming_extends_inherited("Acme.App", "Acme.App")

    def test_unrelated_values(self):
        assert not incoming_extends_inherited("Acme.App", "Other.sln")

    def test_generic_dotted_suffix(self):
        assert incoming_extends_inherited("app.config", "app.config.json")

    def test_non_string(self):
        assert not incoming_extends_inherited(1, "1.sln")


class TestReconcileWithInheritedComputed:
    def test_preserves_established_base(self):
        inherited = {"solution_name": "Acme.App"}
        variables = {"solution_name": "Acme.App.sln", "other": "x"}
        reconcile_with_inherited_computed(inherited, variables)
        assert variables["solution_name"] == "Acme.App"
        assert variables["other"] == "x"

    def test_does_not_touch_unrelated_keys(self):
        inherited = {"solution_name": "Acme.App"}
        variables = {"solution_name": "OtherName.sln"}
        reconcile_with_inherited_computed(inherited, variables)
        assert variables["solution_name"] == "OtherName.sln"


class TestPreferCollectedGlobalValue:
    def test_prefers_inherited_when_collected_adds_suffix(self):
        inherited = {"solution_name": "Acme.App"}
        assert (
            prefer_collected_global_value("Acme.App.sln", inherited, "solution_name")
            == "Acme.App"
        )

    def test_keeps_collected_when_no_inherited(self):
        assert prefer_collected_global_value("Foo.sln", {}, "solution_name") == "Foo.sln"
