from __future__ import annotations

import os

import pytest

import koreanpulse._env as env_mod
from koreanpulse._env import _parse_env_file, load_env_once


@pytest.fixture(autouse=True)
def _reset_loaded():
    """Each test starts with a fresh loader state."""
    env_mod._LOADED = False
    yield
    env_mod._LOADED = False


class TestParseEnvFile:
    def test_basic(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
        assert _parse_env_file(f) == {"FOO": "bar", "BAZ": "qux"}

    def test_quoted_values(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text('FOO="bar baz"\nQUUX=\'hello\'\n', encoding="utf-8")
        assert _parse_env_file(f) == {"FOO": "bar baz", "QUUX": "hello"}

    def test_comments_and_blank(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("# this is a comment\n\nFOO=bar\n# trailing\n", encoding="utf-8")
        assert _parse_env_file(f) == {"FOO": "bar"}

    def test_no_equals_skipped(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("INVALID_LINE\nFOO=bar\n", encoding="utf-8")
        assert _parse_env_file(f) == {"FOO": "bar"}

    def test_empty_value(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("FOO=\n", encoding="utf-8")
        assert _parse_env_file(f) == {"FOO": ""}


class TestLoadEnvOnce:
    def test_does_not_overwrite_existing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KOREANPULSE_TEST_X", "from_real_env")
        f = tmp_path / ".env"
        f.write_text("KOREANPULSE_TEST_X=from_dotenv\n", encoding="utf-8")
        monkeypatch.setenv("KOREANPULSE_ENV_FILE", str(f))

        load_env_once()

        # Real env value wins — dotenv loader honors override=False
        assert os.environ["KOREANPULSE_TEST_X"] == "from_real_env"

    def test_loads_when_var_missing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("KOREANPULSE_TEST_Y", raising=False)
        f = tmp_path / ".env"
        f.write_text("KOREANPULSE_TEST_Y=from_dotenv\n", encoding="utf-8")
        monkeypatch.setenv("KOREANPULSE_ENV_FILE", str(f))

        load_env_once()

        assert os.environ["KOREANPULSE_TEST_Y"] == "from_dotenv"

    def test_idempotent(self, tmp_path, monkeypatch):
        f = tmp_path / ".env"
        f.write_text("KOREANPULSE_TEST_Z=v1\n", encoding="utf-8")
        monkeypatch.setenv("KOREANPULSE_ENV_FILE", str(f))

        load_env_once()
        assert os.environ.get("KOREANPULSE_TEST_Z") == "v1"

        # Modify file and call again — should be no-op
        f.write_text("KOREANPULSE_TEST_Z=v2\n", encoding="utf-8")
        load_env_once()
        assert os.environ.get("KOREANPULSE_TEST_Z") == "v1"  # unchanged

    def test_silent_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KOREANPULSE_ENV_FILE", str(tmp_path / "does_not_exist.env"))
        # Should not raise
        load_env_once()
