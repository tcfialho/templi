"""Testes do lock de escrita do manifesto."""

import pytest
import yaml

from templi.core.manifest_lock import (
    is_manifest_write_locked,
    manifest_lock_path,
    manifest_write_lock,
)
from templi.core.manifest_manager import update_manifest
from templi.core.models import Plugin, PluginMetadata, PluginSpec


def _make_plugin(name: str = "child-plugin") -> Plugin:
    return Plugin(
        schema_version="v3",
        kind="plugin",
        metadata=PluginMetadata(
            name=name,
            display_name=name,
            description="Test",
            version="1.0.0",
        ),
        spec=PluginSpec(type="app"),
        source_directory=".",
    )


class TestManifestWriteLock:
    def test_update_manifest_skips_while_lock_held(self, tmp_path):
        project_dir = str(tmp_path)
        with manifest_write_lock(project_dir):
            assert is_manifest_write_locked(project_dir)
            path = update_manifest(project_dir, _make_plugin("parent"), {"x": 1})
            assert path.endswith("manifest.yaml")
            assert not (tmp_path / ".templi" / "manifest.yaml").exists()

        update_manifest(project_dir, _make_plugin("parent"), {"x": 1})
        content = yaml.safe_load((tmp_path / ".templi" / "manifest.yaml").read_text())
        assert len(content["applied_plugins"]) == 1

    def test_lock_released_after_exception(self, tmp_path):
        project_dir = str(tmp_path)
        with pytest.raises(RuntimeError):
            with manifest_write_lock(project_dir):
                raise RuntimeError("hook failed")

        assert not is_manifest_write_locked(project_dir)
        assert not manifest_lock_path(project_dir).exists()

    def test_stale_lock_removed_when_pid_dead(self, tmp_path, monkeypatch):
        project_dir = str(tmp_path)
        monkeypatch.setattr(
            "templi.core.manifest_lock._pid_is_alive",
            lambda _pid: False,
        )
        lock_path = manifest_lock_path(project_dir)
        lock_path.parent.mkdir(parents=True)
        lock_path.write_text("pid=4242\nstarted=1\n", encoding="utf-8")

        assert not is_manifest_write_locked(project_dir)
        assert not lock_path.exists()

    def test_lock_file_removed_after_context(self, tmp_path):
        project_dir = str(tmp_path)
        with manifest_write_lock(project_dir):
            assert manifest_lock_path(project_dir).exists()

        assert not manifest_lock_path(project_dir).exists()
        assert not is_manifest_write_locked(project_dir)

    def test_nested_apply_is_noop_when_lock_held(self, tmp_path):
        project_dir = str(tmp_path)
        import time

        held = manifest_lock_path(project_dir)
        held.parent.mkdir(parents=True)
        held.write_text(f"pid=4242\nstarted={time.time():.0f}\n", encoding="utf-8")

        import templi.core.manifest_lock as lock_mod

        original = lock_mod._pid_is_alive
        lock_mod._pid_is_alive = lambda pid: True if pid == 4242 else original(pid)
        try:
            with manifest_write_lock(project_dir):
                update_manifest(project_dir, _make_plugin("child"), {"y": 2})
                assert not (tmp_path / ".templi" / "manifest.yaml").exists()
            assert held.exists()
            assert held.read_text(encoding="utf-8").startswith("pid=4242")
        finally:
            lock_mod._pid_is_alive = original
