import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import Settings, settings

def test_settings_default():
    assert settings.default_model == "gemini-3.1-flash-live-preview"
    assert settings.translate_model == "gemini-3.5-transcribe-live"
    assert settings.translation_mode == "simultaneous"
    assert settings.port == 8000
    assert "generativelanguage.googleapis.com" in settings.get_generative_language_ws_endpoint()
    assert "BidiGenerateContentConstrained" in settings.get_live_ws_endpoint()
    assert settings.token_uses == 1
    assert settings.token_ttl_minutes == 30
    assert settings.token_new_session_ttl_minutes == 5
    assert settings.lock_token_constraints is True

def test_settings_env_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_API_KEY=AIzaSyNewTestKey\n"
        "DEFAULT_MODEL=gemini-3.1-flash-live-preview\n"
        "TOKEN_USES=2\n"
        "TOKEN_TTL_MINUTES=45\n"
    )

    s = Settings(env_file=str(env_file))
    # Environment variable overrides .env file (override=False)
    assert s.gemini_api_key == "env-key"
    assert s.default_model == "gemini-3.1-flash-live-preview"
    assert s.token_uses == 2
    assert s.token_ttl_minutes == 45
