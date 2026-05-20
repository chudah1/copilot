from pathlib import Path

from app.config import ENV_FILES, PROJECT_ROOT, Settings


def test_env_files_are_absolute_project_paths():
    assert PROJECT_ROOT.name == "copilot_investor"
    assert all(Path(path).is_absolute() for path in ENV_FILES)
    assert ENV_FILES[0].endswith("/copilot_investor/.env")
    assert ENV_FILES[1].endswith("/copilot_investor/backend/.env")


def test_settings_model_uses_absolute_env_files():
    config_env_files = Settings.model_config.get("env_file")
    assert config_env_files == ENV_FILES
