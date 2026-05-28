"""Testes de credenciais HTTPS via Git credential helper."""

from unittest.mock import patch

from templi.core.git_auth import (
    _credential_fill_input,
    _credentials_from_embedded_remote_url,
    _normalize_repo_url,
    _parse_credential_output,
    porcelain_https_auth,
    porcelain_https_clone_kwargs,
    resolve_https_credentials,
)


class TestCredentialFillInput:
    def test_https_with_path(self):
        payload = _credential_fill_input(
            "https://dev.azure.com/org/proj/_git/repo"
        )
        assert "protocol=https" in payload
        assert "host=dev.azure.com" in payload
        assert "path=org/proj/_git/repo" in payload

    def test_embedded_credentials_not_filled(self):
        user, password = resolve_https_credentials(
            "https://user:token@github.com/org/repo.git"
        )
        assert user == "user"
        assert password == "token"


class TestParseCredentialOutput:
    def test_username_and_password(self):
        stdout = "protocol=https\nhost=example.com\nusername=alice\npassword=secret\n"
        assert _parse_credential_output(stdout) == ("alice", "secret")

    def test_empty_output(self):
        assert _parse_credential_output("") == (None, None)


class TestNormalizeRepoUrl:
    def test_strips_git_suffix_and_user(self):
        a = _normalize_repo_url(
            "https://dev.azure.com/company/Project%20Name/_git/foo.git"
        )
        b = _normalize_repo_url(
            "https://user:pass@dev.azure.com/company/Project%20Name/_git/foo"
        )
        assert a == b


class TestEmbeddedRemoteUrl:
    def test_extracts_credentials(self):
        user, pwd = _credentials_from_embedded_remote_url(
            "https://alice:secret@github.com/org/repo.git"
        )
        assert user == "alice"
        assert pwd == "secret"

    def test_azure_pat_in_username_becomes_password(self):
        user, pwd = _credentials_from_embedded_remote_url(
            "https://pat-token@dev.azure.com/company/org/_git/repo"
        )
        assert user == ""
        assert pwd == "pat-token"


class TestGitCredentialFill:
    def test_fill_via_git_subprocess(self):
        with patch(
            "templi.core.git_auth._git_credential_fill",
            return_value=("svc", "pat"),
        ):
            assert resolve_https_credentials(
                "https://dev.azure.com/org/proj/_git/repo"
            ) == ("svc", "pat")

    def test_porcelain_kwargs_include_auth(self):
        with patch(
            "templi.core.git_auth.resolve_https_credentials",
            return_value=("u", "p"),
        ):
            auth = porcelain_https_auth("https://example.com/a.git")
            assert auth == {"username": "u", "password": "p"}
            clone_kw = porcelain_https_clone_kwargs("https://example.com/a.git")
            assert clone_kw["username"] == "u"
            assert clone_kw["password"] == "p"
            assert "config" in clone_kw

    def test_subprocess_fill_success(self):
        with patch("templi.core.git_auth.subprocess.run") as run_mock:
            run_mock.return_value.returncode = 0
            run_mock.return_value.stdout = (
                "protocol=https\nhost=github.com\nusername=gcm-user\npassword=gcm-pass\n"
            )
            user, password = resolve_https_credentials("https://github.com/org/r.git")
        assert user == "gcm-user"
        assert password == "gcm-pass"
        run_mock.assert_called_once()
        call = run_mock.call_args
        assert call.args[0] == ["git", "credential", "fill"]
        assert "host=github.com" in call.kwargs["input"]
