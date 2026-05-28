"""Testes do hook edit-json — jsonpath inválido não altera o documento."""

import json

from templi.core.models import JsonHookChange
from templi.hooks.edit_json import execute_edit_json_hook


class TestEditJsonSkipInvalidPath:
    def test_skips_empty_bracket_token_without_creating_phantom_keys(self, tmp_path):
        angular = {
            "projects": {
                "msw-plugin-test": {
                    "architect": {
                        "build": {
                            "options": {
                                "assets": ["src/favicon.ico", "src/assets"],
                            }
                        }
                    }
                }
            }
        }
        target = tmp_path / "angular.json"
        target.write_text(json.dumps(angular, indent="\t") + "\n", encoding="utf-8")

        execute_edit_json_hook(
            hook_path="angular.json",
            changes=[
                JsonHookChange(
                    jsonpath="$.projects['{{dx_web_inner_project_name_lower}}'].architect.build.options.assets",
                    update_value='"src/mockServiceWorker.js"',
                )
            ],
            plugin_source_dir=str(tmp_path),
            project_dir=str(tmp_path),
            variables={"dx_web_inner_project_name_lower": ""},
        )

        result = json.loads(target.read_text(encoding="utf-8"))
        assert result == angular
        assert "" not in result["projects"]
        assert "architect" not in result["projects"]

    def test_applies_when_rendered_path_exists(self, tmp_path):
        angular = {
            "projects": {
                "msw-plugin-test": {
                    "architect": {
                        "build": {
                            "options": {
                                "assets": ["src/favicon.ico"],
                            }
                        }
                    }
                }
            }
        }
        target = tmp_path / "angular.json"
        target.write_text(json.dumps(angular, indent="\t") + "\n", encoding="utf-8")

        execute_edit_json_hook(
            hook_path="angular.json",
            changes=[
                JsonHookChange(
                    jsonpath="$.projects['{{dx_web_inner_project_name_lower}}'].architect.build.options.assets",
                    update_value='"src/mockServiceWorker.js"',
                )
            ],
            plugin_source_dir=str(tmp_path),
            project_dir=str(tmp_path),
            variables={"dx_web_inner_project_name_lower": "msw-plugin-test"},
        )

        assets = (
            json.loads(target.read_text(encoding="utf-8"))
            ["projects"]["msw-plugin-test"]["architect"]["build"]["options"]["assets"]
        )
        assert assets == ["src/favicon.ico", "src/mockServiceWorker.js"]

    def test_merges_root_jsonpath_when_target_key_missing(self, tmp_path):
        package = {"devDependencies": {"msw": "^2.3.0"}}
        target = tmp_path / "package.json"
        target.write_text(json.dumps(package, indent="\t") + "\n", encoding="utf-8")

        execute_edit_json_hook(
            hook_path="package.json",
            changes=[
                JsonHookChange(
                    jsonpath="$",
                    update_value='{"msw": {"workerDirectory": ["src"]}}',
                    when_not_exists="$.msw",
                )
            ],
            plugin_source_dir=str(tmp_path),
            project_dir=str(tmp_path),
            variables={},
        )

        result = json.loads(target.read_text(encoding="utf-8"))
        assert result["msw"] == {"workerDirectory": ["src"]}
        assert result["devDependencies"]["msw"] == "^2.3.0"
