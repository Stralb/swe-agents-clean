import os
from pathlib import Path

from src.settings import PROJECT_ROOT, load_settings


def test_load_settings_does_not_depend_on_cwd(tmp_path, monkeypatch):
    gone = tmp_path / "deleted_cwd"
    gone.mkdir()
    old_cwd = Path.cwd()
    try:
        os.chdir(gone)
        gone.rmdir()
        monkeypatch.delenv("CONFIG", raising=False)
        monkeypatch.delenv("DB_PATH", raising=False)
        settings = load_settings()
        assert settings.config_path == PROJECT_ROOT / "config.yml"
        assert settings.db_path == PROJECT_ROOT / "data" / "miner.db"
    finally:
        os.chdir(old_cwd)


def test_relative_config_and_db_path_are_project_root_relative(monkeypatch):
    monkeypatch.setenv("CONFIG", "config.yml")
    monkeypatch.setenv("DB_PATH", "data/test_settings_paths.db")
    settings = load_settings()
    assert settings.config_path == PROJECT_ROOT / "config.yml"
    assert settings.db_path == PROJECT_ROOT / "data" / "test_settings_paths.db"
