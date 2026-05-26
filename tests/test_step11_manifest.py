"""Testes do Step 11 — Manifest Manager."""

import os
import yaml
import pytest

from templi.core.manifest_manager import load_global_inputs, update_manifest
from templi.core.models import Plugin, PluginMetadata, PluginSpec
from templi.core.runtime_config import COMPAT_NAME_ENV, MANIFEST_DIR_ENV, MANIFEST_FILE_ENV


def _make_plugin(name="test-plugin", version="1.0.0") -> Plugin:
    return Plugin(
        schema_version="v3",
        kind="plugin",
        metadata=PluginMetadata(name=name, display_name=name, description="Test", version=version),
        spec=PluginSpec(type="app"),
        source_directory=".",
    )


class TestCreateManifest:
    def test_creates_manifest_directory(self, tmp_path):
        update_manifest(str(tmp_path), _make_plugin(), {})
        assert (tmp_path / ".templi").is_dir()
        assert (tmp_path / ".templi" / "manifest.yaml").exists()

    def test_uses_compat_manifest_directory(self, tmp_path, monkeypatch):
        monkeypatch.setenv(COMPAT_NAME_ENV, "CustomTool")

        path = update_manifest(str(tmp_path), _make_plugin(), {})

        assert path == os.path.join(str(tmp_path), ".customtool", "customtool.yaml")
        assert (tmp_path / ".customtool" / "customtool.yaml").exists()
        assert not (tmp_path / ".templi").exists()

    def test_loads_globals_from_compat_manifest_directory(self, tmp_path, monkeypatch):
        monkeypatch.setenv(COMPAT_NAME_ENV, "CustomTool")

        update_manifest(
            str(tmp_path),
            _make_plugin(),
            {},
            global_inputs={"ecosystem": "nodejs"},
            global_computed_inputs={"service_name": "api"},
        )

        assert load_global_inputs(str(tmp_path)) == {
            "ecosystem": "nodejs",
            "service_name": "api",
        }

    def test_uses_configured_manifest_path_overrides(self, tmp_path, monkeypatch):
        monkeypatch.setenv(COMPAT_NAME_ENV, "CustomTool")
        monkeypatch.setenv(MANIFEST_DIR_ENV, ".legacy-state")
        monkeypatch.setenv(MANIFEST_FILE_ENV, "legacy-manifest.yaml")

        path = update_manifest(
            str(tmp_path),
            _make_plugin(),
            {},
            global_inputs={"ecosystem": "python"},
        )

        assert path == os.path.join(
            str(tmp_path),
            ".legacy-state",
            "legacy-manifest.yaml",
        )
        assert load_global_inputs(str(tmp_path)) == {"ecosystem": "python"}

    def test_rejects_invalid_compat_name(self, tmp_path, monkeypatch):
        monkeypatch.setenv(COMPAT_NAME_ENV, "custom-tool")

        with pytest.raises(ValueError, match=COMPAT_NAME_ENV):
            update_manifest(str(tmp_path), _make_plugin(), {})

    def test_manifest_has_applied_plugins(self, tmp_path):
        update_manifest(str(tmp_path), _make_plugin(), {"name": "value"})
        content = yaml.safe_load((tmp_path / ".templi" / "manifest.yaml").read_text())
        assert "applied_plugins" in content
        assert len(content["applied_plugins"]) == 1
        assert content["applied_plugins"][0]["name"] == "test-plugin"
        assert content["applied_plugins"][0]["version"] == "1.0.0"

    def test_inputs_saved(self, tmp_path):
        update_manifest(str(tmp_path), _make_plugin(), {"ecosystem": "dotnet", "debug": True})
        content = yaml.safe_load((tmp_path / ".templi" / "manifest.yaml").read_text())
        inputs = content["applied_plugins"][0]["inputs"]
        assert inputs["ecosystem"] == "dotnet"
        assert inputs["debug"] == "true"

    def test_list_inputs_serialized_as_csv(self, tmp_path):
        update_manifest(str(tmp_path), _make_plugin(), {"app_types": ["webapi", "worker"]})
        content = yaml.safe_load((tmp_path / ".templi" / "manifest.yaml").read_text())
        assert content["applied_plugins"][0]["inputs"]["app_types"] == "webapi,worker"


class TestAppendManifest:
    def test_appends_second_plugin(self, tmp_path):
        update_manifest(str(tmp_path), _make_plugin("plugin-a"), {})
        update_manifest(str(tmp_path), _make_plugin("plugin-b"), {})

        content = yaml.safe_load((tmp_path / ".templi" / "manifest.yaml").read_text())
        assert len(content["applied_plugins"]) == 2
        names = [p["name"] for p in content["applied_plugins"]]
        assert "plugin-a" in names
        assert "plugin-b" in names


class TestTimestamp:
    def test_has_applied_at(self, tmp_path):
        update_manifest(str(tmp_path), _make_plugin(), {})
        content = yaml.safe_load((tmp_path / ".templi" / "manifest.yaml").read_text())
        assert "applied_at" in content["applied_plugins"][0]


class TestRobustness:
    def test_empty_inputs(self, tmp_path):
        path = update_manifest(str(tmp_path), _make_plugin(), {})
        assert os.path.isfile(path)

    def test_corrupt_existing_manifest(self, tmp_path):
        manifest_dir = tmp_path / ".templi"
        manifest_dir.mkdir()
        (manifest_dir / "manifest.yaml").write_text("{{invalid yaml content}}::: @@@@")
        # Should not crash — creates new entry
        update_manifest(str(tmp_path), _make_plugin(), {})
        content = yaml.safe_load((tmp_path / ".templi" / "manifest.yaml").read_text())
        assert len(content["applied_plugins"]) == 1
