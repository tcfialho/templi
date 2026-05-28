"""Testes de resolução de plugin local ou via Git."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from templi.core.plugin_ref import is_git_reference, resolve_plugin_directory


class TestIsGitReference:
    def test_https_url(self):
        assert is_git_reference("https://github.com/org/repo.git")

    def test_git_scp_rejected_for_resolve(self):
        with pytest.raises(ValueError, match="HTTPS"):
            resolve_plugin_directory("git@github.com:org/repo.git")

    def test_local_path(self, tmp_path):
        assert not is_git_reference(str(tmp_path / "my-plugin"))


class TestResolvePluginDirectoryLocal:
    def test_local_directory(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.yaml").write_text("schema-version: v2\n", encoding="utf-8")

        resolved = resolve_plugin_directory(str(plugin_dir))
        assert resolved == str(plugin_dir.resolve())

    def test_local_with_subpath(self, tmp_path):
        root = tmp_path / "monorepo"
        plugin_dir = root / "stack" / "plugin-a"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.yaml").write_text("schema-version: v2\n", encoding="utf-8")

        resolved = resolve_plugin_directory(str(root), subpath="stack/plugin-a")
        assert resolved == str(plugin_dir.resolve())

    def test_missing_plugin_yaml(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="plugin.yaml"):
            resolve_plugin_directory(str(empty))


class TestResolvePluginDirectoryGit:
    def test_first_resolve_clones(self, tmp_path):
        cache = tmp_path / "cache"
        clone_calls: list[tuple] = []

        def fake_clone(url, dest, git_ref):
            clone_calls.append((url, dest, git_ref))
            dest.mkdir(parents=True, exist_ok=True)
            (dest / ".git").mkdir()
            (dest / "plugin.yaml").write_text("schema-version: v2\n", encoding="utf-8")

        with (
            patch("templi.core.plugin_ref._cache_dir_for", return_value=cache),
            patch("templi.core.plugin_ref._clone_repository", side_effect=fake_clone),
        ):
            resolve_plugin_directory(
                "https://example.com/org/repo.git", git_ref="main"
            )

        assert clone_calls

    def test_second_resolve_fetches_instead_of_clone(self, tmp_path):
        cache = tmp_path / "cache"
        repo = cache / "repo"
        repo.mkdir(parents=True)
        (repo / ".git").mkdir()
        (repo / "plugin.yaml").write_text("schema-version: v2\n", encoding="utf-8")

        fetch_calls: list[tuple] = []

        def fake_fetch(url, dest, git_ref):
            fetch_calls.append((url, dest, git_ref))

        with (
            patch("templi.core.plugin_ref._cache_dir_for", return_value=cache),
            patch("templi.core.plugin_ref._fetch_and_reset", side_effect=fake_fetch),
            patch("templi.core.plugin_ref._clone_repository") as clone_mock,
        ):
            resolve_plugin_directory(
                "https://example.com/org/repo.git", git_ref="main"
            )

        clone_mock.assert_not_called()
        assert fetch_calls[0][2] == "main"

    def test_fetch_failure_falls_back_to_clone(self, tmp_path):
        cache = tmp_path / "cache"
        repo = cache / "repo"
        repo.mkdir(parents=True)
        (repo / ".git").mkdir()

        def fake_fetch(*_args, **_kwargs):
            raise OSError("network error")

        def fake_clone(url, dest, git_ref):
            dest.mkdir(parents=True, exist_ok=True)
            (dest / ".git").mkdir()
            (dest / "plugin.yaml").write_text("schema-version: v2\n", encoding="utf-8")

        with (
            patch("templi.core.plugin_ref._cache_dir_for", return_value=cache),
            patch("templi.core.plugin_ref._fetch_and_reset", side_effect=fake_fetch),
            patch("templi.core.plugin_ref._clone_repository", side_effect=fake_clone),
        ):
            resolve_plugin_directory("https://example.com/org/repo.git")

        assert (cache / "repo" / "plugin.yaml").is_file()

    def test_skip_plugin_yaml_for_repo_root(self, tmp_path):
        cache = tmp_path / "cache"

        def fake_clone(url, dest, git_ref):
            dest.mkdir(parents=True, exist_ok=True)
            (dest / ".git").mkdir()
            (dest / "README.md").write_text("repo\n", encoding="utf-8")

        with (
            patch("templi.core.plugin_ref._cache_dir_for", return_value=cache),
            patch("templi.core.plugin_ref._clone_repository", side_effect=fake_clone),
        ):
            resolved = resolve_plugin_directory(
                "https://example.com/org/monorepo.git",
                require_plugin_yaml=False,
            )

        assert resolved.endswith("repo")
