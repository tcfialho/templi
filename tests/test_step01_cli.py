"""Testes do Step 01 — CLI Parser, Printer e File Utils."""

import json
import os
import pytest

from templi.cli.parser import parse_extra_args, parse_inputs_json
from templi.cli.printer import (
    WARNING_MESSAGE,
    print_applied,
    print_applying,
    print_error,
    print_warning_outside_workspace,
)
from templi.utils.file_utils import (
    copy_file,
    ensure_directory,
    is_binary_file,
    read_file,
    read_text_or_detect_binary,
    write_file,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CA-01.5: Parse de extra args
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseExtraArgs:
    def test_parse_standard_pairs(self):
        args = ["--plugin_name", "meu-plugin", "--ecosystem", "dotnet", "--app_types", "webapi,worker"]
        result = parse_extra_args(args)
        assert result == {
            "plugin_name": "meu-plugin",
            "ecosystem": "dotnet",
            "app_types": "webapi,worker",
        }

    def test_parse_empty_list(self):
        assert parse_extra_args([]) == {}

    def test_parse_flag_without_value(self):
        args = ["--verbose"]
        result = parse_extra_args(args)
        assert result == {"verbose": ""}

    def test_parse_mixed_flags_and_pairs(self):
        args = ["--name", "teste", "--debug", "--version", "1.0"]
        result = parse_extra_args(args)
        assert result["name"] == "teste"
        assert result["version"] == "1.0"

    def test_parse_value_with_spaces(self):
        args = ["--description", "Plugin de teste para Kafka"]
        result = parse_extra_args(args)
        assert result["description"] == "Plugin de teste para Kafka"

    def test_parse_empty_value(self):
        args = ["--repository_url", ""]
        result = parse_extra_args(args)
        assert result["repository_url"] == ""


# ═══════════════════════════════════════════════════════════════════════════════
# CA-01.6: Parse de inputs JSON
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseInputsJson:
    def test_parse_valid_json(self):
        json_str = '{"plugin_name": "meu-plugin", "ecosystem": "dotnet"}'
        result = parse_inputs_json(json_str)
        assert result == {"plugin_name": "meu-plugin", "ecosystem": "dotnet"}

    def test_parse_empty_string(self):
        assert parse_inputs_json("") == {}

    def test_parse_none(self):
        assert parse_inputs_json(None) == {}

    def test_parse_whitespace(self):
        assert parse_inputs_json("   ") == {}

    def test_parse_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_inputs_json("{invalid}")

    def test_parse_json_with_list_value(self):
        json_str = '{"app_types": ["webapi", "worker"]}'
        result = parse_inputs_json(json_str)
        assert result["app_types"] == ["webapi", "worker"]


# ═══════════════════════════════════════════════════════════════════════════════
# Printer
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrinter:
    def test_warning_message_content(self):
        assert "Não há suporte" in WARNING_MESSAGE
        assert "workspace ativo" in WARNING_MESSAGE

    def test_print_applying(self, capsys):
        print_applying("C:\\path\\to\\plugin")
        captured = capsys.readouterr()
        assert "> Aplicando o plugin C:\\path\\to\\plugin." in captured.out

    def test_print_applied(self, capsys):
        print_applied("C:\\path\\to\\plugin")
        captured = capsys.readouterr()
        assert "- Plugin C:\\path\\to\\plugin aplicado." in captured.out

    def test_print_error(self, capsys):
        print_error("algo deu errado")
        captured = capsys.readouterr()
        assert "Erro: algo deu errado" in captured.err

    def test_print_warning_outside_workspace(self, capsys):
        print_warning_outside_workspace()
        captured = capsys.readouterr()
        assert "Aviso" in captured.out
        assert "workspace ativo" in captured.out


# ═══════════════════════════════════════════════════════════════════════════════
# File Utils
# ═══════════════════════════════════════════════════════════════════════════════

class TestFileUtils:
    def test_ensure_directory(self, tmp_path):
        target = os.path.join(str(tmp_path), "a", "b", "c")
        ensure_directory(target)
        assert os.path.isdir(target)

    def test_ensure_directory_already_exists(self, tmp_path):
        ensure_directory(str(tmp_path))
        assert os.path.isdir(str(tmp_path))

    def test_write_and_read_file(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "test.txt")
        write_file(file_path, "conteúdo de teste")
        assert read_file(file_path) == "conteúdo de teste"

    def test_write_file_creates_parent_dirs(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "sub", "dir", "test.txt")
        write_file(file_path, "ok")
        assert read_file(file_path) == "ok"

    def test_write_file_utf8(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "utf8.txt")
        write_file(file_path, "açúcar café résumé")
        assert read_file(file_path) == "açúcar café résumé"

    def test_copy_file_basic(self, tmp_path):
        source = os.path.join(str(tmp_path), "source.txt")
        target = os.path.join(str(tmp_path), "target.txt")
        write_file(source, "conteúdo original")
        copy_file(source, target)
        assert read_file(target) == "conteúdo original"

    def test_copy_file_creates_parent_dirs(self, tmp_path):
        source = os.path.join(str(tmp_path), "source.txt")
        target = os.path.join(str(tmp_path), "sub", "dir", "target.txt")
        write_file(source, "ok")
        copy_file(source, target)
        assert read_file(target) == "ok"

    def test_is_binary_file_text(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "text.txt")
        write_file(file_path, "hello world")
        assert is_binary_file(file_path) is False

    def test_is_binary_file_binary(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "binary.bin")
        with open(file_path, "wb") as file_handle:
            file_handle.write(b"\x00\x01\x02\x03")
        assert is_binary_file(file_path) is True

    def test_is_binary_file_empty(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "empty.txt")
        write_file(file_path, "")
        assert is_binary_file(file_path) is False

    def test_read_text_or_detect_binary_text(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "text.txt")
        write_file(file_path, "açúcar")
        assert read_text_or_detect_binary(file_path) == "açúcar"

    def test_read_text_or_detect_binary_binary(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "image.bin")
        with open(file_path, "wb") as file_handle:
            file_handle.write(b"\x89PNG\r\n\x1a\n\x00\x01\x02")
        assert read_text_or_detect_binary(file_path) is None

    def test_read_text_or_detect_binary_normalizes_crlf(self, tmp_path):
        # CRLF must collapse to LF so write_file's text mode doesn't double the CR
        file_path = os.path.join(str(tmp_path), "crlf.txt")
        with open(file_path, "wb") as file_handle:
            file_handle.write(b"a\r\nb\r\nc")
        assert read_text_or_detect_binary(file_path) == "a\nb\nc"

    def test_read_text_or_detect_binary_normalizes_cr_only(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "cr.txt")
        with open(file_path, "wb") as file_handle:
            file_handle.write(b"a\rb\rc")
        assert read_text_or_detect_binary(file_path) == "a\nb\nc"

    def test_read_text_or_detect_binary_normalizes_mixed_newlines(self, tmp_path):
        file_path = os.path.join(str(tmp_path), "mixed.txt")
        with open(file_path, "wb") as file_handle:
            file_handle.write(b"a\r\nb\rc\n")
        assert read_text_or_detect_binary(file_path) == "a\nb\nc\n"

    def test_read_text_or_detect_binary_raises_on_invalid_utf8(self, tmp_path):
        # Sem \x00 nos primeiros 8KB e sem ser UTF-8 válido → mesmo contrato que
        # read_file: UnicodeDecodeError sobe para o caller.
        file_path = os.path.join(str(tmp_path), "latin1.txt")
        with open(file_path, "wb") as file_handle:
            file_handle.write(b"caf\xe9")  # 'café' em latin-1, inválido em UTF-8
        with pytest.raises(UnicodeDecodeError):
            read_text_or_detect_binary(file_path)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Integration (via Click CliRunner)
# ═══════════════════════════════════════════════════════════════════════════════

from click.testing import CliRunner
from templi.main import cli


class TestCliIntegration:
    def setup_method(self):
        self.runner = CliRunner()

    def test_cli_help(self):
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "apply" in result.output

    def test_apply_help(self):
        result = self.runner.invoke(cli, ["apply", "--help"])
        assert result.exit_code == 0
        assert "plugin" in result.output

    def test_apply_plugin_help(self):
        result = self.runner.invoke(cli, ["apply", "plugin", "--help"])
        assert result.exit_code == 0
        assert "NAME_OR_PATH" in result.output
        assert "--skip-warning" in result.output
        assert "--non-interactive" in result.output
        assert "--inputs-json" in result.output

    def test_apply_plugin_path_not_found(self):
        result = self.runner.invoke(cli, ["apply", "plugin", "C:\\caminho\\inexistente"])
        assert result.exit_code == 1
        assert "plugin.yaml não encontrado" in result.output or "plugin.yaml não encontrado" in (result.output + str(result.exception or ""))

    def test_apply_plugin_skip_warning_no_aviso(self, tmp_path):
        result = self.runner.invoke(cli, ["apply", "plugin", str(tmp_path), "-s"])
        # Não deve conter a mensagem de aviso (embora falhe por falta de plugin.yaml)
        assert "workspace ativo" not in result.output

    def test_apply_plugin_with_existing_plugin_yaml(self, tmp_path):
        # Criar plugin.yaml mínimo
        plugin_yaml_path = os.path.join(str(tmp_path), "plugin.yaml")
        with open(plugin_yaml_path, "w") as file_handle:
            file_handle.write("schema-version: v3\nkind: plugin\nmetadata:\n  name: test\n  display-name: test\n  description: test\n  version: 1.0.0\nspec:\n  type: app\n")

        result = self.runner.invoke(cli, ["apply", "plugin", str(tmp_path), "-s"])
        assert "Aplicando o plugin" in result.output
        assert "aplicado" in result.output

    def test_apply_plugin_shows_warning_without_skip(self, tmp_path):
        plugin_yaml_path = os.path.join(str(tmp_path), "plugin.yaml")
        with open(plugin_yaml_path, "w") as file_handle:
            file_handle.write("schema-version: v3\nkind: plugin\nmetadata:\n  name: test\n  display-name: test\n  description: test\n  version: 1.0.0\nspec:\n  type: app\n")

        result = self.runner.invoke(cli, ["apply", "plugin", str(tmp_path)])
        assert "workspace ativo" in result.output

    def test_apply_plugin_with_extra_args(self, tmp_path):
        plugin_yaml_path = os.path.join(str(tmp_path), "plugin.yaml")
        with open(plugin_yaml_path, "w") as file_handle:
            file_handle.write("schema-version: v3\nkind: plugin\nmetadata:\n  name: test\n  display-name: test\n  description: test\n  version: 1.0.0\nspec:\n  type: app\n")

        result = self.runner.invoke(cli, [
            "apply", "plugin", str(tmp_path), "-s",
            "--plugin_name", "meu-plugin",
            "--ecosystem", "dotnet"
        ])
        assert result.exit_code == 0
        assert "aplicado" in result.output
