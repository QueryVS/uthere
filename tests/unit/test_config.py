from __future__ import annotations

from pathlib import Path

from uthere.config import get_setting, read_env_file_value


def test_read_env_file_value(tmp_path):
    env_file = tmp_path / "uthere.env"
    env_file.write_text("\n# comment\nUTHERE_DB='/var/lib/uthere/uthere.db'\n", encoding="utf-8")

    assert read_env_file_value(env_file, "UTHERE_DB") == "/var/lib/uthere/uthere.db"


def test_get_setting_prefers_environment(tmp_path, monkeypatch):
    env_file = tmp_path / "uthere.env"
    env_file.write_text("UTHERE_DB=/var/lib/uthere/uthere.db\n", encoding="utf-8")
    monkeypatch.setenv("UTHERE_DB", "/tmp/uthere.db")

    assert get_setting("UTHERE_DB", "fallback", (Path(env_file),)) == "/tmp/uthere.db"
