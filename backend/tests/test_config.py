from pathlib import Path

from app.config import ENV_FILES, PROJECT_ROOT, Settings


def test_env_files_are_absolute_project_paths():
    # PROJECT_ROOT is the repo root (the dir containing backend/), whatever the
    # checkout folder is named — don't hardcode it.
    assert (PROJECT_ROOT / "backend").is_dir()
    assert all(Path(path).is_absolute() for path in ENV_FILES)
    assert Path(ENV_FILES[0]) == PROJECT_ROOT / ".env"
    assert Path(ENV_FILES[1]) == PROJECT_ROOT / "backend" / ".env"


def test_settings_model_uses_absolute_env_files():
    config_env_files = Settings.model_config.get("env_file")
    assert config_env_files == ENV_FILES
