import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import Settings, settings

def test_settings_default():
    assert settings.default_model == "gemini-2.0-flash-exp"
    assert settings.port == 8000
    assert "generativelanguage.googleapis.com" in settings.get_generative_language_ws_endpoint()

def test_settings_dotenv_override(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "old-key")

    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=AIzaSyNewTestKey\nDEFAULT_MODEL=gemini-2.0-flash-exp\n")

    s = Settings(env_file=str(env_file))
    assert s.gemini_api_key == "AIzaSyNewTestKey"
    assert s.default_model == "gemini-2.0-flash-exp"
