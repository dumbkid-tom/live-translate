import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app, ip_request_history
from backend.gemini_live import build_interpreter_prompt, build_live_session_config, TokenService, resolve_language_code
from backend.config import settings

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["provider"] == "gemini_live_ephemeral"
    assert "BidiGenerateContentConstrained" in data["endpoint"]
    assert "has_api_key" in data
    assert data["token_uses"] == 1
    assert data["token_ttl_minutes"] == 30

def test_index_route():
    response = client.get("/")
    assert response.status_code == 200

def test_build_interpreter_prompt():
    prompt = build_interpreter_prompt("Spanish", "English")
    assert "Spanish" in prompt
    assert "from English" in prompt

    prompt_no_src = build_interpreter_prompt("Japanese")
    assert "Japanese" in prompt_no_src
    assert "from " not in prompt_no_src

def test_resolve_language_code():
    assert resolve_language_code("Spanish") == "es"
    assert resolve_language_code("es") == "es"
    assert resolve_language_code("French") == "fr"
    assert resolve_language_code("ja") == "ja"
    assert resolve_language_code("zh-CN") == "zh-cn"
    assert resolve_language_code("nl") == "nl"
    assert resolve_language_code("UnknownLang") == "en"
    assert resolve_language_code("12345") == "en"
    assert resolve_language_code(None) == "en"
    assert resolve_language_code("") == "en"

def test_build_live_session_config():
    # Simultaneous mode (default)
    cfg = build_live_session_config("French", translation_mode="simultaneous")
    setup = cfg["setup"]
    assert setup["model"] == "models/gemini-3.5-live-translate-preview"
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert setup["generationConfig"]["translationConfig"]["targetLanguageCode"] == "fr"
    assert "realtimeInputConfig" not in setup

    # Turn-based fallback mode
    cfg_tb = build_live_session_config("French", "audio", "gemini-3.1-flash-live-preview", silence_duration_ms=600, translation_mode="turn_based")
    setup_tb = cfg_tb["setup"]
    assert setup_tb["model"] == "models/gemini-3.1-flash-live-preview"
    assert setup_tb["realtimeInputConfig"]["activityHandling"] == "NO_INTERRUPTION"
    assert setup_tb["realtimeInputConfig"]["automaticActivityDetection"]["silenceDurationMs"] == 600
    assert setup_tb["realtimeInputConfig"]["automaticActivityDetection"]["endOfSpeechSensitivity"] == "END_SENSITIVITY_HIGH"

def test_token_service_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    service = TokenService()
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set"):
        service.create("Spanish")

def test_token_service_create_mocked(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "fake-api-key")

    mock_token_obj = MagicMock()
    mock_token_obj.name = "auth_tokens/mock_123456"

    mock_genai_client = MagicMock()
    mock_genai_client.auth_tokens.create.return_value = mock_token_obj

    with patch("backend.gemini_live.genai.Client", return_value=mock_genai_client):
        service = TokenService()

        # Simultaneous token
        result = service.create("German", "audio", translation_mode="simultaneous")
        assert result["token"] == "auth_tokens/mock_123456"
        assert "access_token=auth_tokens/mock_123456" in result["ws_endpoint"]
        assert result["model"] == "models/gemini-3.5-live-translate-preview"
        assert result["translation_mode"] == "simultaneous"
        assert result["target_language_code"] == "de"

        # Turn-based token
        result_tb = service.create("German", "audio", model="gemini-3.1-flash-live-preview", translation_mode="turn_based")
        assert result_tb["model"] == "models/gemini-3.1-flash-live-preview"
        assert result_tb["translation_mode"] == "turn_based"
        assert result_tb["setup"]["realtimeInputConfig"]["activityHandling"] == "NO_INTERRUPTION"

def test_api_token_endpoint_success(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "fake-api-key")

    mock_token_obj = MagicMock()
    mock_token_obj.name = "auth_tokens/mock_7890"

    mock_genai_client = MagicMock()
    mock_genai_client.auth_tokens.create.return_value = mock_token_obj

    ip_request_history.clear()

    with patch("backend.gemini_live.genai.Client", return_value=mock_genai_client):
        response = client.post("/api/token", json={
            "target_language": "Italian",
            "mode": "audio",
            "translation_mode": "turn_based",
            "silence_duration_ms": 600
        })
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "auth_tokens/mock_7890"
        assert "ws_endpoint" in data
        assert "setup" in data
        assert data["translation_mode"] == "turn_based"
        assert data["target_language_code"] == "it"
        assert data["setup"]["realtimeInputConfig"]["automaticActivityDetection"]["silenceDurationMs"] == 600

def test_api_token_endpoint_validation_bounds(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "fake-api-key")

    ip_request_history.clear()

    # silence_duration_ms too low (< 100)
    response = client.post("/api/token", json={"silence_duration_ms": 50})
    assert response.status_code == 422

    # silence_duration_ms too high (> 2000)
    response = client.post("/api/token", json={"silence_duration_ms": 3000})
    assert response.status_code == 422

def test_api_token_endpoint_translation_mode_validation(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "fake-api-key")

    mock_token_obj = MagicMock()
    mock_token_obj.name = "auth_tokens/mock_tm_val"

    mock_genai_client = MagicMock()
    mock_genai_client.auth_tokens.create.return_value = mock_token_obj

    ip_request_history.clear()

    # Invalid translation mode
    response = client.post("/api/token", json={"translation_mode": "invalid_mode"})
    assert response.status_code == 422

    # Valid translation modes
    with patch("backend.gemini_live.genai.Client", return_value=mock_genai_client):
        resp1 = client.post("/api/token", json={"translation_mode": "simultaneous"})
        assert resp1.status_code == 200
        assert resp1.json()["translation_mode"] == "simultaneous"

        resp2 = client.post("/api/token", json={"translation_mode": "turn_based"})
        assert resp2.status_code == 200
        assert resp2.json()["translation_mode"] == "turn_based"

def test_token_service_locks_constraints_structure(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "fake-api-key")
    monkeypatch.setattr(settings, "lock_token_constraints", True)

    mock_token_obj = MagicMock()
    mock_token_obj.name = "auth_tokens/mock_constraints_check"

    mock_genai_client = MagicMock()
    mock_genai_client.auth_tokens.create.return_value = mock_token_obj

    with patch("backend.gemini_live.genai.Client", return_value=mock_genai_client):
        service = TokenService()
        result = service.create("German", "audio", translation_mode="simultaneous", echo_target_language=True)

        call_args = mock_genai_client.auth_tokens.create.call_args
        assert call_args is not None
        config_arg = call_args.kwargs.get("config")
        assert config_arg is not None

        # Check live_connect_constraints in CreateAuthTokenConfig
        constraints = config_arg.live_connect_constraints
        assert constraints is not None
        assert constraints.model == "models/gemini-3.5-live-translate-preview"
        assert constraints.config.translation_config.target_language_code == "de"
        assert constraints.config.translation_config.echo_target_language is True

def test_api_token_endpoint_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "fake-api-key")
    monkeypatch.setattr(settings, "token_rate_limit_per_minute", 2)

    mock_token_obj = MagicMock()
    mock_token_obj.name = "auth_tokens/mock_rl"

    mock_genai_client = MagicMock()
    mock_genai_client.auth_tokens.create.return_value = mock_token_obj

    ip_request_history.clear()

    with patch("backend.gemini_live.genai.Client", return_value=mock_genai_client):
        r1 = client.post("/api/token", json={"target_language": "Spanish"})
        assert r1.status_code == 200

        r2 = client.post("/api/token", json={"target_language": "Spanish"})
        assert r2.status_code == 200

        r3 = client.post("/api/token", json={"target_language": "Spanish"})
        assert r3.status_code == 429
        assert "Rate limit exceeded" in r3.json()["detail"]
